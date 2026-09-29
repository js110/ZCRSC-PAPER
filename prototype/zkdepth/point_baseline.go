package zkdepth

import (
    "fmt"
    "math/big"

    "github.com/consensys/gnark/frontend"
    "github.com/consensys/gnark/std/math/cmp"
)

// PointCircuit is a deliberately weaker lower-bound baseline.
// It proves only that one private point lies inside a public policy box.
// It authenticates no source evidence and provides no Byzantine robustness.
type PointCircuit struct {
    DomainLo []frontend.Variable `gnark:",public"`
    DomainHi []frontend.Variable `gnark:",public"`
    PolicyLo []frontend.Variable `gnark:",public"`
    PolicyHi []frontend.Variable `gnark:",public"`
    Point    []frontend.Variable

    D    int `gnark:"-"`
    Bits int `gnark:"-"`
}

func NewPointCircuit(d, bits int) *PointCircuit {
    if d < 1 || bits < 2 || bits > 32 {
        panic("invalid point circuit shape")
    }
    return &PointCircuit{
        DomainLo: make([]frontend.Variable, d),
        DomainHi: make([]frontend.Variable, d),
        PolicyLo: make([]frontend.Variable, d),
        PolicyHi: make([]frontend.Variable, d),
        Point:    make([]frontend.Variable, d),
        D: d, Bits: bits,
    }
}

func (c *PointCircuit) Define(api frontend.API) error {
    if c.D < 1 || c.Bits < 2 || c.Bits > 32 ||
        len(c.DomainLo) != c.D || len(c.DomainHi) != c.D ||
        len(c.PolicyLo) != c.D || len(c.PolicyHi) != c.D || len(c.Point) != c.D {
        return fmt.Errorf("invalid point circuit parameters")
    }
    bound := new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), uint(c.Bits)), big.NewInt(1))
    comparator := cmp.NewBoundedComparator(api, bound, false)
    for a := 0; a < c.D; a++ {
        api.ToBinary(c.DomainLo[a], c.Bits)
        api.ToBinary(c.DomainHi[a], c.Bits)
        api.ToBinary(c.PolicyLo[a], c.Bits)
        api.ToBinary(c.PolicyHi[a], c.Bits)
        api.ToBinary(c.Point[a], c.Bits)
        comparator.AssertIsLessEq(c.DomainLo[a], c.PolicyLo[a])
        comparator.AssertIsLessEq(c.PolicyLo[a], c.PolicyHi[a])
        comparator.AssertIsLessEq(c.PolicyHi[a], c.DomainHi[a])
        comparator.AssertIsLessEq(c.DomainLo[a], c.Point[a])
        comparator.AssertIsLessEq(c.Point[a], c.DomainHi[a])
        comparator.AssertIsLessEq(c.PolicyLo[a], c.Point[a])
        comparator.AssertIsLessEq(c.Point[a], c.PolicyHi[a])
    }
    return nil
}

func NewPointAssignment(d, bits int) *PointCircuit {
    a := NewPointCircuit(d, bits)
    for axis := 0; axis < d; axis++ {
        a.DomainLo[axis] = 0
        a.DomainHi[axis] = 31
        a.PolicyLo[axis] = 10
        a.PolicyHi[axis] = 20
        a.Point[axis] = 15
    }
    return a
}
