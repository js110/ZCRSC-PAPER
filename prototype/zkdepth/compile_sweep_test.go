package zkdepth

import (
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
	"testing"
)

// Solver controls for the newly swept non-default subset thresholds.
func TestCompileSweepThresholdBinding(t *testing.T) {
	for _, k := range []int{2, 3} {
		c := NewCircuit(4, 2, 16)
		c.SubsetThreshold = k
		cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, c)
		if err != nil {
			t.Fatal(err)
		}
		a, err := NewValidAssignment(4, 2, 16)
		if err != nil {
			t.Fatal(err)
		}
		a.Threshold = k
		w, err := frontend.NewWitness(a, ecc.BN254.ScalarField())
		if err != nil {
			t.Fatal(err)
		}
		if err = cs.IsSolved(w); err != nil {
			t.Fatalf("k=%d valid fixture: %v", k, err)
		}
		a.Threshold = 1
		w, err = frontend.NewWitness(a, ecc.BN254.ScalarField())
		if err != nil {
			t.Fatal(err)
		}
		if err = cs.IsSolved(w); err == nil {
			t.Fatalf("k=%d accepted substituted threshold", k)
		}
	}
}
