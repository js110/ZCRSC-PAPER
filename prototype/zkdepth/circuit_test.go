package zkdepth

import (
	"math/big"
	"testing"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

func makeAssignment(t *testing.T, decision int) *Circuit {
	t.Helper()
	assignment, err := NewAssignment(5, 2, 16, decision)
	if err != nil {
		t.Fatal(err)
	}
	return assignment
}

func TestGroth16ProofAndNegativeControls(t *testing.T) {
	t.Run("depth", func(t *testing.T) { testBackend(t, 0) })
	t.Run("subset", func(t *testing.T) { testBackend(t, 4) })
}

func testBackend(t *testing.T, subset int) {
	shape := NewCircuit(5, 2, 16)
	shape.SubsetThreshold = subset
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, shape)
	if err != nil {
		t.Fatal(err)
	}
	pk, vk, err := groth16.Setup(ccs)
	if err != nil {
		t.Fatal(err)
	}

	for _, decision := range []int{
		DecisionValid, DecisionInvalid, DecisionAmbiguous, DecisionEvidenceFailure,
	} {
		assignment := makeAssignment(t, decision)
		witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
		if err != nil {
			t.Fatal(err)
		}
		proof, err := groth16.Prove(ccs, pk, witness)
		if err != nil {
			t.Fatalf("decision %d did not produce a proof: %v", decision, err)
		}
		publicWitness, err := witness.Public()
		if err != nil {
			t.Fatal(err)
		}
		if err := groth16.Verify(proof, vk, publicWitness); err != nil {
			t.Fatalf("decision %d proof did not verify: %v", decision, err)
		}
	}

	wrongDecision := makeAssignment(t, DecisionValid)
	wrongDecision.Decision = DecisionInvalid
	wrongWitness, err := frontend.NewWitness(wrongDecision, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := groth16.Prove(ccs, pk, wrongWitness); err == nil {
		t.Fatal("wrong public decision unexpectedly produced a proof")
	}

	tampered := makeAssignment(t, DecisionValid)
	tampered.BoxLo[0][0] = 12
	tamperedWitness, err := frontend.NewWitness(tampered, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := groth16.Prove(ccs, pk, tamperedWitness); err == nil {
		t.Fatal("box tampering without a new issuer signature produced a proof")
	}

	duplicateIssuer := makeAssignment(t, DecisionValid)
	duplicateIssuer.PublicKeys[1] = duplicateIssuer.PublicKeys[0]
	duplicateWitness, err := frontend.NewWitness(duplicateIssuer, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := groth16.Prove(ccs, pk, duplicateWitness); err == nil {
		t.Fatal("duplicate issuer keys unexpectedly produced a proof")
	}
	contextTampered := makeAssignment(t, DecisionValid)
	contextTampered.Context = 123
	contextWitness, err := frontend.NewWitness(contextTampered, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	if err := ccs.IsSolved(contextWitness); err == nil {
		t.Fatal("changed context accepted without re-signing")
	}
	// The whole domain has no outside slabs. Exercise their inactive branches.
	wholeDomain := makeAssignment(t, DecisionValid)
	for a := 0; a < wholeDomain.D; a++ {
		wholeDomain.PolicyLo[a] = 0
		wholeDomain.PolicyHi[a] = 31
	}
	wholeWitness, err := frontend.NewWitness(wholeDomain, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	if err := ccs.IsSolved(wholeWitness); err != nil {
		t.Fatalf("whole-domain policy failed: %v", err)
	}
}

func TestMessageEncodingIsCanonicalFieldElement(t *testing.T) {
	message, err := EncodeSignedMessage(9, 0, []int64{1, 2}, []int64{3, 4})
	if err != nil {
		t.Fatal(err)
	}
	if len(message) != fr.Bytes {
		t.Fatalf("unexpected digest length: %d", len(message))
	}
	if new(big.Int).SetBytes(message).Cmp(ecc.BN254.ScalarField()) >= 0 {
		t.Fatal("MiMC digest is not canonical in the BN254 scalar field")
	}
}
