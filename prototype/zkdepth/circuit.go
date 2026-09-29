package zkdepth

import (
	"fmt"
	"math/big"

	tedwards "github.com/consensys/gnark-crypto/ecc/twistededwards"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/algebra/native/twistededwards"
	stdmimc "github.com/consensys/gnark/std/hash/mimc"
	"github.com/consensys/gnark/std/math/cmp"
	stdeddsa "github.com/consensys/gnark/std/signature/eddsa"
)

const (
	DecisionValid = iota
	DecisionInvalid
	DecisionAmbiguous
	DecisionEvidenceFailure
)

// Circuit proves robust policy classification for N private D-dimensional
// inclusive integer boxes. Each box is signed by one distinct public issuer.
// N, D, and Bits are compile-time shape parameters and are not witnesses.
type Circuit struct {
	Context   frontend.Variable   `gnark:",public"`
	DomainLo  []frontend.Variable `gnark:",public"`
	DomainHi  []frontend.Variable `gnark:",public"`
	PolicyLo  []frontend.Variable `gnark:",public"`
	PolicyHi  []frontend.Variable `gnark:",public"`
	Threshold frontend.Variable   `gnark:",public"`
	Decision  frontend.Variable   `gnark:",public"`

	PublicKeys []stdeddsa.PublicKey `gnark:",public"`
	BoxLo      [][]frontend.Variable
	BoxHi      [][]frontend.Variable
	Signatures []stdeddsa.Signature

	N     int         `gnark:"-"`
	D     int         `gnark:"-"`
	Bits  int         `gnark:"-"`
	Curve tedwards.ID `gnark:"-"`
	// SubsetThreshold is zero for lower-corner depth, or a fixed public k
	// for exact subset enumeration. The verifier selects the circuit key.
	SubsetThreshold int `gnark:"-"`
}

func NewCircuit(n, d, bits int) *Circuit {
	if n < 2 || d < 1 || bits < 2 || bits > 32 || uint64(n) >= uint64(1)<<uint(bits) {
		panic("invalid circuit shape")
	}
	c := &Circuit{
		DomainLo:   make([]frontend.Variable, d),
		DomainHi:   make([]frontend.Variable, d),
		PolicyLo:   make([]frontend.Variable, d),
		PolicyHi:   make([]frontend.Variable, d),
		PublicKeys: make([]stdeddsa.PublicKey, n),
		BoxLo:      make([][]frontend.Variable, n),
		BoxHi:      make([][]frontend.Variable, n),
		Signatures: make([]stdeddsa.Signature, n),
		N:          n,
		D:          d,
		Bits:       bits,
		Curve:      tedwards.BN254,
	}
	for i := 0; i < n; i++ {
		c.BoxLo[i] = make([]frontend.Variable, d)
		c.BoxHi[i] = make([]frontend.Variable, d)
	}
	return c
}

func boolAnd(api frontend.API, values ...frontend.Variable) frontend.Variable {
	result := frontend.Variable(1)
	for _, value := range values {
		result = api.Mul(result, value)
	}
	return result
}

func boolOr(api frontend.API, left, right frontend.Variable) frontend.Variable {
	return api.Sub(1, api.Mul(api.Sub(1, left), api.Sub(1, right)))
}

func maxValue(
	api frontend.API,
	comparator *cmp.BoundedComparator,
	left, right frontend.Variable,
) frontend.Variable {
	leftLEQRight := comparator.IsLessEq(left, right)
	return api.Select(leftLEQRight, right, left)
}

func (c *Circuit) validateShape() error {
	if c.N < 2 || c.D < 1 || c.Bits < 2 || c.Bits > 32 || uint64(c.N) >= uint64(1)<<uint(c.Bits) || c.Curve != tedwards.BN254 {
		return fmt.Errorf("invalid circuit parameters")
	}
	if len(c.DomainLo) != c.D || len(c.DomainHi) != c.D ||
		len(c.PolicyLo) != c.D || len(c.PolicyHi) != c.D ||
		len(c.PublicKeys) != c.N || len(c.BoxLo) != c.N ||
		len(c.BoxHi) != c.N || len(c.Signatures) != c.N {
		return fmt.Errorf("invalid circuit allocation")
	}
	for i := 0; i < c.N; i++ {
		if len(c.BoxLo[i]) != c.D || len(c.BoxHi[i]) != c.D {
			return fmt.Errorf("invalid box allocation")
		}
	}
	return nil
}

func (c *Circuit) Define(api frontend.API) error {
	if err := c.validateShape(); err != nil {
		return err
	}

	curve, err := twistededwards.NewEdCurve(api, c.Curve)
	if err != nil {
		return err
	}
	comparisonBound := new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), uint(c.Bits)), big.NewInt(1))
	comparator := cmp.NewBoundedComparator(api, comparisonBound, false)

	// Public task bounds and all private coordinates are range constrained.
	// Context is a public field digest, not a coordinate.  It is deliberately
	// left at the native scalar-field width so deployments can bind a full task
	// transcript instead of a Bits-bit toy identifier.
	api.ToBinary(c.Threshold, c.Bits)
	api.ToBinary(c.Decision, 2)
	api.AssertIsLessOrEqual(1, c.Threshold)
	api.AssertIsLessOrEqual(c.Threshold, c.N)
	for axis := 0; axis < c.D; axis++ {
		api.ToBinary(c.DomainLo[axis], c.Bits)
		api.ToBinary(c.DomainHi[axis], c.Bits)
		api.ToBinary(c.PolicyLo[axis], c.Bits)
		api.ToBinary(c.PolicyHi[axis], c.Bits)
		comparator.AssertIsLessEq(c.DomainLo[axis], c.PolicyLo[axis])
		comparator.AssertIsLessEq(c.PolicyLo[axis], c.PolicyHi[axis])
		comparator.AssertIsLessEq(c.PolicyHi[axis], c.DomainHi[axis])
	}

	for i := 0; i < c.N; i++ {
		// The signed message binds the task/report context, fixed roster slot,
		// and every lower/upper coordinate of this private evidence box.
		messageHasher, hashErr := stdmimc.NewMiMC(api)
		if hashErr != nil {
			return hashErr
		}
		messageHasher.Write(c.Context, i+1)
		for axis := 0; axis < c.D; axis++ {
			api.ToBinary(c.BoxLo[i][axis], c.Bits)
			api.ToBinary(c.BoxHi[i][axis], c.Bits)
			comparator.AssertIsLessEq(c.DomainLo[axis], c.BoxLo[i][axis])
			comparator.AssertIsLessEq(c.BoxLo[i][axis], c.BoxHi[i][axis])
			comparator.AssertIsLessEq(c.BoxHi[i][axis], c.DomainHi[axis])
			messageHasher.Write(c.BoxLo[i][axis], c.BoxHi[i][axis])
		}
		message := messageHasher.Sum()
		signatureHasher, hashErr := stdmimc.NewMiMC(api)
		if hashErr != nil {
			return hashErr
		}
		if err := stdeddsa.Verify(
			curve, c.Signatures[i], message, c.PublicKeys[i], &signatureHasher,
		); err != nil {
			return err
		}
	}

	// The public roster must contain distinct trust-domain keys.
	for i := 0; i < c.N; i++ {
		for j := i + 1; j < c.N; j++ {
			equalX := api.IsZero(api.Sub(c.PublicKeys[i].A.X, c.PublicKeys[j].A.X))
			equalY := api.IsZero(api.Sub(c.PublicKeys[i].A.Y, c.PublicKeys[j].A.Y))
			api.AssertIsEqual(api.Mul(equalX, equalY), 0)
		}
	}

	var inside frontend.Variable
	outside := frontend.Variable(0)
	if c.SubsetThreshold > 0 {
		if c.SubsetThreshold > c.N {
			return fmt.Errorf("invalid subset threshold")
		}
		api.AssertIsEqual(c.Threshold, c.SubsetThreshold)
		inside, outside = c.subsetReachability(api, comparator)
	} else {
		inside = c.regionReachable(api, comparator, c.PolicyLo, c.PolicyHi, 1)
		for axis := 0; axis < c.D; axis++ {
			lowActive := comparator.IsLess(c.DomainLo[axis], c.PolicyLo[axis])
			lowLo := append([]frontend.Variable(nil), c.DomainLo...)
			lowHi := append([]frontend.Variable(nil), c.DomainHi...)
			lowHi[axis] = api.Select(lowActive, api.Sub(c.PolicyLo[axis], 1), c.DomainLo[axis])
			outside = boolOr(api, outside, c.regionReachable(api, comparator, lowLo, lowHi, lowActive))

			highActive := comparator.IsLess(c.PolicyHi[axis], c.DomainHi[axis])
			highLo := append([]frontend.Variable(nil), c.DomainLo...)
			highHi := append([]frontend.Variable(nil), c.DomainHi...)
			highLo[axis] = api.Select(highActive, api.Add(c.PolicyHi[axis], 1), c.DomainHi[axis])
			outside = boolOr(api, outside, c.regionReachable(api, comparator, highLo, highHi, highActive))
		}
	}

	valid := boolAnd(api, inside, api.Sub(1, outside))
	invalid := boolAnd(api, api.Sub(1, inside), outside)
	ambiguous := boolAnd(api, inside, outside)
	failure := boolAnd(api, api.Sub(1, inside), api.Sub(1, outside))
	expectedDecision := api.Add(invalid, api.Mul(2, ambiguous), api.Mul(3, failure))
	api.AssertIsEqual(c.Decision, expectedDecision)
	api.AssertIsEqual(api.Add(valid, invalid, ambiguous, failure), 1)
	return nil
}

// subsetReachability checks every k-way intersection exactly, using the same
// signatures, coordinate checks and public outputs as the depth backend.
func (c *Circuit) subsetReachability(api frontend.API, comparator *cmp.BoundedComparator) (frontend.Variable, frontend.Variable) {
	inside, outside := frontend.Variable(0), frontend.Variable(0)
	var enumerate func(int, []int)
	enumerate = func(start int, selected []int) {
		if len(selected) < c.SubsetThreshold {
			for i := start; i <= c.N-(c.SubsetThreshold-len(selected)); i++ {
				enumerate(i+1, append(selected, i))
			}
			return
		}
		nonempty, intersects, contained := frontend.Variable(1), frontend.Variable(1), frontend.Variable(1)
		for a := 0; a < c.D; a++ {
			lo, hi := c.BoxLo[selected[0]][a], c.BoxHi[selected[0]][a]
			for _, i := range selected[1:] {
				lo = maxValue(api, comparator, lo, c.BoxLo[i][a])
				hi = api.Select(comparator.IsLessEq(hi, c.BoxHi[i][a]), hi, c.BoxHi[i][a])
			}
			nonempty = boolAnd(api, nonempty, comparator.IsLessEq(lo, hi))
			intersects = boolAnd(api, intersects, comparator.IsLessEq(lo, c.PolicyHi[a]), comparator.IsLessEq(c.PolicyLo[a], hi))
			contained = boolAnd(api, contained, comparator.IsLessEq(c.PolicyLo[a], lo), comparator.IsLessEq(hi, c.PolicyHi[a]))
		}
		inside = boolOr(api, inside, boolAnd(api, nonempty, intersects))
		outside = boolOr(api, outside, boolAnd(api, nonempty, api.Sub(1, contained)))
	}
	enumerate(0, nil)
	return inside, outside
}

// regionReachable returns 1 exactly when at least Threshold private boxes have
// a common point in the inclusive public query box. It evaluates all N^D
// lower-corner candidates; duplicates are harmless.
func (c *Circuit) regionReachable(
	api frontend.API,
	comparator *cmp.BoundedComparator,
	queryLo []frontend.Variable,
	queryHi []frontend.Variable,
	active frontend.Variable,
) frontend.Variable {
	api.AssertIsBoolean(active)
	combinations := 1
	for axis := 0; axis < c.D; axis++ {
		combinations *= c.N
	}
	reachable := frontend.Variable(0)
	for encoded := 0; encoded < combinations; encoded++ {
		indices := make([]int, c.D)
		value := encoded
		for axis := 0; axis < c.D; axis++ {
			indices[axis] = value % c.N
			value /= c.N
		}
		point := make([]frontend.Variable, c.D)
		for axis := 0; axis < c.D; axis++ {
			point[axis] = maxValue(api, comparator, c.BoxLo[indices[axis]][axis], queryLo[axis])
		}

		depth := frontend.Variable(0)
		for box := 0; box < c.N; box++ {
			covered := active
			for axis := 0; axis < c.D; axis++ {
				covered = boolAnd(
					api,
					covered,
					comparator.IsLessEq(queryLo[axis], point[axis]),
					comparator.IsLessEq(point[axis], queryHi[axis]),
					comparator.IsLessEq(c.BoxLo[box][axis], point[axis]),
					comparator.IsLessEq(point[axis], c.BoxHi[box][axis]),
				)
			}
			depth = api.Add(depth, covered)
		}
		atLeastThreshold := comparator.IsLessEq(c.Threshold, depth)
		reachable = boolOr(api, reachable, atLeastThreshold)
	}
	return api.Mul(active, reachable)
}
