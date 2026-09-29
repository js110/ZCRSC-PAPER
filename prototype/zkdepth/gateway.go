package zkdepth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"sync"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
)

// Task is verifier-authorized configuration. TrustDomain labels are assigned by
// the administrator, never by a reporting vehicle. Labels cannot demonstrate
// independent physical control; they enforce the configured enrollment policy.
type Issuer struct {
	PublicKey   []byte
	TrustDomain string
}
type Task struct {
	ID                                     string
	CircuitID                              string
	CoordinateConvention                   string
	CalibrationProfile                     string
	DomainLo, DomainHi, PolicyLo, PolicyHi []int64
	Bits, Threshold                        int
	Roster                                 []Issuer
}
type Challenge struct {
	Nonce     string
	ExpiresAt int64
}
type contextTranscript struct {
	Version      string
	Task         Task
	Challenge    Challenge
	ReportSHA256 string
}

func (t Task) validate() error {
	d := len(t.DomainLo)
	if t.ID == "" || t.CircuitID == "" || t.CoordinateConvention == "" || t.CalibrationProfile == "" || d == 0 || t.Bits < 2 || t.Bits > 32 || len(t.Roster) < 2 || t.Threshold < 1 || t.Threshold > len(t.Roster) {
		return fmt.Errorf("invalid task metadata")
	}
	if len(t.DomainHi) != d || len(t.PolicyLo) != d || len(t.PolicyHi) != d || uint64(len(t.Roster)) >= uint64(1)<<uint(t.Bits) {
		return fmt.Errorf("invalid dimensions or count")
	}
	for a := 0; a < d; a++ {
		if t.DomainLo[a] < 0 || t.DomainLo[a] > t.PolicyLo[a] || t.PolicyLo[a] > t.PolicyHi[a] || t.PolicyHi[a] > t.DomainHi[a] || uint64(t.DomainHi[a]) >= uint64(1)<<uint(t.Bits) {
			return fmt.Errorf("invalid bounds")
		}
	}
	keys, domains := map[string]bool{}, map[string]bool{}
	for _, issuer := range t.Roster {
		key := hex.EncodeToString(issuer.PublicKey)
		if len(issuer.PublicKey) != 32 || issuer.TrustDomain == "" || keys[key] || domains[issuer.TrustDomain] {
			return fmt.Errorf("duplicate or invalid enrolled issuer")
		}
		keys[key], domains[issuer.TrustDomain] = true, true
	}
	return nil
}

// ContextDigest hashes a deterministic JSON struct (no maps), then reduces into
// the BN254 scalar field. Both endpoints must use this exact versioned encoding.
// The report hash binds report bytes; it does not attest their physical truth.
func ContextDigest(t Task, c Challenge, report []byte) (*big.Int, error) {
	if err := t.validate(); err != nil {
		return nil, err
	}
	if len(c.Nonce) != 64 || c.ExpiresAt <= 0 {
		return nil, fmt.Errorf("invalid challenge")
	}
	if _, err := hex.DecodeString(c.Nonce); err != nil {
		return nil, err
	}
	rh := sha256.Sum256(report)
	encoded, err := json.Marshal(contextTranscript{"PCVCS-PaperA-context-v1", t, c, hex.EncodeToString(rh[:])})
	if err != nil {
		return nil, err
	}
	h := sha256.Sum256(encoded)
	return new(big.Int).Mod(new(big.Int).SetBytes(h[:]), ecc.BN254.ScalarField()), nil
}

// Statement reconstructs public inputs from verifier-approved task metadata.
// Private witness fields are unused in PublicOnly witness creation.
func Statement(t Task, c Challenge, report []byte, decision int) (*Circuit, error) {
	context, err := ContextDigest(t, c, report)
	if err != nil {
		return nil, err
	}
	if decision < 0 || decision > 3 {
		return nil, fmt.Errorf("invalid decision")
	}
	s := NewCircuit(len(t.Roster), len(t.DomainLo), t.Bits)
	s.Context, s.Threshold, s.Decision = context, t.Threshold, decision
	for a := range t.DomainLo {
		s.DomainLo[a] = t.DomainLo[a]
		s.DomainHi[a] = t.DomainHi[a]
		s.PolicyLo[a] = t.PolicyLo[a]
		s.PolicyHi[a] = t.PolicyHi[a]
	}
	for i, issuer := range t.Roster {
		s.PublicKeys[i].Assign(s.Curve, issuer.PublicKey)
	}
	return s, nil
}

// Gateway is an in-process report-verification harness. Production needs a
// durable, cross-instance replay store and authenticated task/key provisioning.
type Gateway struct {
	task    Task
	vk      groth16.VerifyingKey
	mu      sync.Mutex
	pending map[string]Challenge
}

func NewGateway(t Task, vk groth16.VerifyingKey) (*Gateway, error) {
	if err := t.validate(); err != nil {
		return nil, err
	}
	if vk == nil {
		return nil, fmt.Errorf("missing verification key")
	}
	// Snapshot all slices so callers cannot mutate the trusted configuration.
	encoded, err := json.Marshal(t)
	if err != nil {
		return nil, err
	}
	var snapshot Task
	if err = json.Unmarshal(encoded, &snapshot); err != nil {
		return nil, err
	}
	return &Gateway{task: snapshot, vk: vk, pending: make(map[string]Challenge)}, nil
}

func (g *Gateway) Issue(now, ttl int64) (Challenge, error) {
	if now <= 0 || ttl <= 0 || ttl > 3600 || now > int64(^uint64(0)>>1)-ttl {
		return Challenge{}, fmt.Errorf("invalid challenge lifetime")
	}
	var nonce [32]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return Challenge{}, err
	}
	c := Challenge{hex.EncodeToString(nonce[:]), now + ttl}
	g.mu.Lock()
	defer g.mu.Unlock()
	for k, v := range g.pending {
		if now >= v.ExpiresAt {
			delete(g.pending, k)
		}
	}
	g.pending[c.Nonce] = c
	return c, nil
}

// Submit returns report eligibility only after a proof is verified against
// trusted public inputs. A successful decision consumes its nonce atomically.
// Invalid proofs do not consume a challenge. The lock prevents racing replays.
func (g *Gateway) Submit(nonce string, report []byte, decision int, proof groth16.Proof, now int64) (bool, error) {
	g.mu.Lock()
	defer g.mu.Unlock()
	c, ok := g.pending[nonce]
	if !ok {
		return false, fmt.Errorf("unknown or consumed challenge")
	}
	if now <= 0 || now >= c.ExpiresAt {
		return false, fmt.Errorf("expired challenge")
	}
	if proof == nil {
		return false, fmt.Errorf("missing proof")
	}
	statement, err := Statement(g.task, c, report, decision)
	if err != nil {
		return false, err
	}
	public, err := frontend.NewWitness(statement, ecc.BN254.ScalarField(), frontend.PublicOnly())
	if err != nil {
		return false, err
	}
	if err = groth16.Verify(proof, g.vk, public); err != nil {
		return false, err
	}
	delete(g.pending, nonce)
	return decision == DecisionValid, nil
}
