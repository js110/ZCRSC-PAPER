package zkdepth

import (
	"crypto/rand"
	"fmt"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	fr_mimc "github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	tedwards "github.com/consensys/gnark-crypto/ecc/twistededwards"
	cryptoeddsa "github.com/consensys/gnark-crypto/signature/eddsa"
)

func fieldEncoding(values ...int64) []byte {
	result := make([]byte, 0, len(values)*fr.Bytes)
	for _, value := range values {
		var element fr.Element
		element.SetInt64(value)
		encoded := element.Bytes()
		result = append(result, encoded[:]...)
	}
	return result
}

// EncodeSignedMessage mirrors the in-circuit MiMC encoding of one evidence box.
func EncodeSignedMessage(context int64, slot int, lo, hi []int64) ([]byte, error) {
	return EncodeSignedFieldMessage(big.NewInt(context), slot, lo, hi)
}

// EncodeSignedFieldMessage accepts the full canonical scalar-field context.
func EncodeSignedFieldMessage(context *big.Int, slot int, lo, hi []int64) ([]byte, error) {
	if len(lo) == 0 || len(lo) != len(hi) {
		return nil, fmt.Errorf("invalid box dimensions")
	}
	h := fr_mimc.NewMiMC()
	if context == nil || context.Sign() < 0 || context.Cmp(fr.Modulus()) >= 0 || slot < 0 {
		return nil, fmt.Errorf("invalid canonical context or slot")
	}
	var element fr.Element
	element.SetBigInt(context)
	encodedContext := element.Bytes()
	if _, err := h.Write(encodedContext[:]); err != nil {
		return nil, err
	}
	values := []int64{int64(slot + 1)}
	for axis := range lo {
		values = append(values, lo[axis], hi[axis])
	}
	if _, err := h.Write(fieldEncoding(values...)); err != nil {
		return nil, err
	}
	return h.Sum(nil), nil
}

// NewAssignment constructs deterministic geometry for one of the four robust
// decisions, with fresh issuer keys and real EdDSA signatures. Cryptographic
// randomness is intentionally not deterministic.
func NewAssignment(n, d, bits, decision int) (*Circuit, error) {
	if n < 3 || n > 8 || d < 1 || bits < 5 || bits > 32 {
		return nil, fmt.Errorf("fixture requires 3<=n<=8, d>=1, 5<=bits<=32")
	}
	if decision < DecisionValid || decision > DecisionEvidenceFailure {
		return nil, fmt.Errorf("invalid decision")
	}
	assignment := NewCircuit(n, d, bits)
	// Larger than 2^bits: this catches accidental coordinate-width constraints
	// on the public transcript digest.
	const context int64 = 1 << 20
	assignment.Context = context
	assignment.Threshold = n - 1
	assignment.Decision = decision
	for axis := 0; axis < d; axis++ {
		assignment.DomainLo[axis] = 0
		assignment.DomainHi[axis] = 31
		assignment.PolicyLo[axis] = 10
		assignment.PolicyHi[axis] = 20
	}
	for i := 0; i < n; i++ {
		lo := make([]int64, d)
		hi := make([]int64, d)
		for axis := 0; axis < d; axis++ {
			switch decision {
			case DecisionValid:
				if i == n-1 {
					lo[axis], hi[axis] = 0, 31
				} else {
					lo[axis], hi[axis] = 11, 18
				}
			case DecisionInvalid:
				if i == n-1 {
					lo[axis], hi[axis] = 0, 31
				} else {
					lo[axis], hi[axis] = 2, 7
				}
			case DecisionAmbiguous:
				if i == n-1 {
					lo[axis], hi[axis] = 0, 31
				} else {
					lo[axis], hi[axis] = 8, 12
				}
			case DecisionEvidenceFailure:
				// With threshold n-1, distinct singleton boxes have no
				// feasible point either inside or outside the policy.
				lo[axis], hi[axis] = int64(2+4*i), int64(2+4*i)
			}
			assignment.BoxLo[i][axis] = lo[axis]
			assignment.BoxHi[i][axis] = hi[axis]
		}
		signer, err := cryptoeddsa.New(tedwards.BN254, rand.Reader)
		if err != nil {
			return nil, err
		}
		message, err := EncodeSignedMessage(context, i, lo, hi)
		if err != nil {
			return nil, err
		}
		signature, err := signer.Sign(message, fr_mimc.NewMiMC())
		if err != nil {
			return nil, err
		}
		assignment.PublicKeys[i].Assign(tedwards.BN254, signer.Public().Bytes())
		assignment.Signatures[i].Assign(tedwards.BN254, signature)
	}
	return assignment, nil
}

func NewValidAssignment(n, d, bits int) (*Circuit, error) {
	return NewAssignment(n, d, bits, DecisionValid)
}
