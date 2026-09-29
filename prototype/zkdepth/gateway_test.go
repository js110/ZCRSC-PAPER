package zkdepth

import (
	"crypto/rand"
	"fmt"
	"github.com/consensys/gnark-crypto/ecc"
	fr_mimc "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	tedwards "github.com/consensys/gnark-crypto/ecc/twistededwards"
	cryptoeddsa "github.com/consensys/gnark-crypto/signature/eddsa"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
	"sync"
	"sync/atomic"
	"testing"
)

func TestGatewayBoundReportAndReplay(t *testing.T) {
	task := Task{ID: "road-observation-01", CircuitID: "subset-n3-d2-k2-b16", CoordinateConvention: "local-x-metres-t-seconds-v1", CalibrationProfile: "bounded-demo-v1", DomainLo: []int64{0, 0}, DomainHi: []int64{31, 31}, PolicyLo: []int64{10, 10}, PolicyHi: []int64{20, 20}, Bits: 16, Threshold: 2}
	sign := make([]func([]byte) ([]byte, error), 3)
	for i, domain := range []string{"authority-A", "authority-B", "authority-C"} {
		signer, err := cryptoeddsa.New(tedwards.BN254, rand.Reader)
		if err != nil {
			t.Fatal(err)
		}
		task.Roster = append(task.Roster, Issuer{signer.Public().Bytes(), domain})
		sign[i] = func(m []byte) ([]byte, error) { return signer.Sign(m, fr_mimc.NewMiMC()) }
	}
	shape := NewCircuit(3, 2, 16)
	shape.SubsetThreshold = 2
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, shape)
	if err != nil {
		t.Fatal(err)
	}
	pk, vk, err := groth16.Setup(ccs)
	if err != nil {
		t.Fatal(err)
	}
	gateway, err := NewGateway(task, vk)
	if err != nil {
		t.Fatal(err)
	}
	challenge, err := gateway.Issue(1000, 60)
	if err != nil {
		t.Fatal(err)
	}
	report := []byte("surface observation at event 42")
	assignment, err := Statement(task, challenge, report, DecisionValid)
	if err != nil {
		t.Fatal(err)
	}
	context, err := ContextDigest(task, challenge, report)
	if err != nil {
		t.Fatal(err)
	}
	if context.BitLen() <= 64 {
		t.Fatal("unexpectedly short transcript digest")
	}
	for i := 0; i < 3; i++ {
		lo, hi := []int64{11, 11}, []int64{18, 18}
		for a := 0; a < 2; a++ {
			assignment.BoxLo[i][a] = lo[a]
			assignment.BoxHi[i][a] = hi[a]
		}
		m, err := EncodeSignedFieldMessage(context, i, lo, hi)
		if err != nil {
			t.Fatal(err)
		}
		sig, err := sign[i](m)
		if err != nil {
			t.Fatal(err)
		}
		assignment.Signatures[i].Assign(tedwards.BN254, sig)
	}
	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	proof, err := groth16.Prove(ccs, pk, witness)
	if err != nil {
		t.Fatal(err)
	}
	t.Run("report-substitution", func(t *testing.T) {
		if _, err := gateway.Submit(challenge.Nonce, []byte("changed report"), 0, proof, 1001); err == nil {
			t.Fatal("substituted report accepted")
		}
	})
	t.Run("decision-substitution", func(t *testing.T) {
		if _, err := gateway.Submit(challenge.Nonce, report, 1, proof, 1001); err == nil {
			t.Fatal("substituted decision accepted")
		}
	})
	t.Run("expired", func(t *testing.T) {
		if _, err := gateway.Submit(challenge.Nonce, report, 0, proof, 1060); err == nil {
			t.Fatal("expired challenge accepted")
		}
	})
	t.Run("unknown-nonce", func(t *testing.T) {
		if _, err := gateway.Submit("unknown", report, 0, proof, 1001); err == nil {
			t.Fatal("unknown challenge accepted")
		}
	})
	t.Run("different-challenge", func(t *testing.T) {
		other, e := gateway.Issue(1000, 60)
		if e != nil {
			t.Fatal(e)
		}
		if _, err := gateway.Submit(other.Nonce, report, 0, proof, 1001); err == nil {
			t.Fatal("proof moved to another challenge")
		}
	})
	t.Run("public-policy-substitution", func(t *testing.T) {
		altered := task
		altered.Threshold = 1
		s, e := Statement(altered, challenge, report, 0)
		if e != nil {
			t.Fatal(e)
		}
		public, e := frontend.NewWitness(s, ecc.BN254.ScalarField(), frontend.PublicOnly())
		if e != nil {
			t.Fatal(e)
		}
		if err := groth16.Verify(proof, vk, public); err == nil {
			t.Fatal("unauthorized threshold accepted")
		}
	})
	for decision, name := range []string{"valid", "invalid", "ambiguous", "evidence-failure"} {
		t.Run("decision-lifecycle-"+name, func(t *testing.T) {
			c, err := gateway.Issue(1000, 60)
			if err != nil {
				t.Fatal(err)
			}
			s, err := Statement(task, c, report, decision)
			if err != nil {
				t.Fatal(err)
			}
			ctx, err := ContextDigest(task, c, report)
			if err != nil {
				t.Fatal(err)
			}
			for i := 0; i < 3; i++ {
				lo, hi := []int64{11, 11}, []int64{18, 18}
				switch decision {
				case DecisionInvalid:
					lo, hi = []int64{2, 2}, []int64{7, 7}
				case DecisionAmbiguous:
					lo, hi = []int64{8, 8}, []int64{12, 12}
				case DecisionEvidenceFailure:
					point := int64(2 + 4*i)
					lo, hi = []int64{point, point}, []int64{point, point}
				}
				for a := 0; a < 2; a++ {
					s.BoxLo[i][a], s.BoxHi[i][a] = lo[a], hi[a]
				}
				m, err := EncodeSignedFieldMessage(ctx, i, lo, hi)
				if err != nil {
					t.Fatal(err)
				}
				sig, err := sign[i](m)
				if err != nil {
					t.Fatal(err)
				}
				s.Signatures[i].Assign(tedwards.BN254, sig)
			}
			w, err := frontend.NewWitness(s, ecc.BN254.ScalarField())
			if err != nil {
				t.Fatal(err)
			}
			p, err := groth16.Prove(ccs, pk, w)
			if err != nil {
				t.Fatal(err)
			}
			// Failed submissions must leave this challenge usable for the real decision.
			if _, err := gateway.Submit(c.Nonce, report, decision, nil, 1001); err == nil {
				t.Fatal("missing proof accepted")
			}
			for forged := 0; forged < 4; forged++ {
				if forged == decision {
					continue
				}
				t.Run(fmt.Sprintf("reject-code-%d", forged), func(t *testing.T) {
					if _, err := gateway.Submit(c.Nonce, report, forged, p, 1001); err == nil {
						t.Fatal("proof accepted for a different decision")
					}
				})
			}
			eligible, err := gateway.Submit(c.Nonce, report, decision, p, 1001)
			if err != nil || eligible != (decision == DecisionValid) {
				t.Fatalf("decision %d: eligible=%v err=%v", decision, eligible, err)
			}
			if _, err := gateway.Submit(c.Nonce, report, decision, p, 1001); err == nil {
				t.Fatal("verified decision did not consume challenge")
			}
		})
	}
	// Mutating caller-owned slices cannot alter the verifier's enrolled snapshot.
	task.PolicyLo[0] = 0
	t.Run("concurrent-replay", func(t *testing.T) {
		var successes atomic.Int32
		var workers sync.WaitGroup
		for i := 0; i < 8; i++ {
			workers.Add(1)
			go func() {
				defer workers.Done()
				ok, err := gateway.Submit(challenge.Nonce, report, 0, proof, 1001)
				if err == nil && ok {
					successes.Add(1)
				}
			}()
		}
		workers.Wait()
		if successes.Load() != 1 {
			t.Fatalf("accepted %d copies", successes.Load())
		}
	})
	t.Run("duplicate-trust-domain", func(t *testing.T) {
		task.Roster[1].TrustDomain = task.Roster[0].TrustDomain
		if _, err := NewGateway(task, vk); err == nil {
			t.Fatal("duplicate authority accepted")
		}
	})
}
