package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sort"
	"time"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"

	zkdepth "pcvcs-paper-a/zkdepth"
)

type summary struct {
	N                    int       `json:"n"`
	D                    int       `json:"d"`
	Bits                 int       `json:"bits"`
	Repetitions          int       `json:"repetitions"`
	Constraints          int       `json:"constraints"`
	CompileMS            float64   `json:"compile_ms"`
	SetupMS              float64   `json:"setup_ms"`
	WitnessMS            float64   `json:"witness_ms"`
	ProveMS              []float64 `json:"prove_ms"`
	VerifyMS             []float64 `json:"verify_ms"`
	ProveMedianMS        float64   `json:"prove_median_ms"`
	VerifyMedianMS       float64   `json:"verify_median_ms"`
	ProofBytes           int       `json:"proof_bytes"`
	PublicWitnessBytes   int       `json:"public_witness_bytes"`
	GoVersion            string    `json:"go_version"`
	GOOS                 string    `json:"goos"`
	GOARCH               string    `json:"goarch"`
	GnarkVersion         string    `json:"gnark_version"`
	Backend              string    `json:"backend"`
	Curve                string    `json:"curve"`
	CoordinateConvention string    `json:"coordinate_convention"`
	GeometryBackend      string    `json:"geometry_backend"`
}

func elapsedMS(start time.Time) float64 {
	return float64(time.Since(start).Microseconds()) / 1000.0
}

func median(values []float64) float64 {
	copyOfValues := append([]float64(nil), values...)
	sort.Float64s(copyOfValues)
	middle := len(copyOfValues) / 2
	if len(copyOfValues)%2 == 1 {
		return copyOfValues[middle]
	}
	return (copyOfValues[middle-1] + copyOfValues[middle]) / 2
}

func main() {
	n := flag.Int("n", 5, "number of signed evidence boxes")
	d := flag.Int("d", 2, "box dimension")
	bits := flag.Int("bits", 16, "coordinate bit width")
	repetitions := flag.Int("repetitions", 5, "proof repetitions after one setup")
	output := flag.String("output", "", "optional JSON output path")
	geometry := flag.String("geometry", "depth", "depth or subset")
	flag.Parse()
	if *repetitions < 1 {
		fmt.Fprintln(os.Stderr, "repetitions must be positive")
		os.Exit(2)
	}

	shape := zkdepth.NewCircuit(*n, *d, *bits)
	if *geometry == "subset" {
		shape.SubsetThreshold = *n - 1
	} else if *geometry != "depth" {
		panic("unsupported geometry backend")
	}
	started := time.Now()
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, shape)
	if err != nil {
		panic(err)
	}
	compileMS := elapsedMS(started)

	started = time.Now()
	pk, vk, err := groth16.Setup(ccs)
	if err != nil {
		panic(err)
	}
	setupMS := elapsedMS(started)

	assignment, err := zkdepth.NewValidAssignment(*n, *d, *bits)
	if err != nil {
		panic(err)
	}
	started = time.Now()
	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	if err != nil {
		panic(err)
	}
	publicWitness, err := witness.Public()
	if err != nil {
		panic(err)
	}
	witnessMS := elapsedMS(started)

	proveTimes := make([]float64, 0, *repetitions)
	verifyTimes := make([]float64, 0, *repetitions)
	proofBytes := 0
	for i := 0; i < *repetitions; i++ {
		started = time.Now()
		proof, err := groth16.Prove(ccs, pk, witness)
		if err != nil {
			panic(err)
		}
		proveTimes = append(proveTimes, elapsedMS(started))

		started = time.Now()
		if err := groth16.Verify(proof, vk, publicWitness); err != nil {
			panic(err)
		}
		verifyTimes = append(verifyTimes, elapsedMS(started))
		if i == 0 {
			var proofBuffer bytes.Buffer
			if _, err := proof.WriteTo(&proofBuffer); err != nil {
				panic(err)
			}
			proofBytes = proofBuffer.Len()
		}
	}
	var publicBuffer bytes.Buffer
	if _, err := publicWitness.WriteTo(&publicBuffer); err != nil {
		panic(err)
	}

	result := summary{
		N:                    *n,
		D:                    *d,
		Bits:                 *bits,
		Repetitions:          *repetitions,
		Constraints:          ccs.GetNbConstraints(),
		CompileMS:            compileMS,
		SetupMS:              setupMS,
		WitnessMS:            witnessMS,
		ProveMS:              proveTimes,
		VerifyMS:             verifyTimes,
		ProveMedianMS:        median(proveTimes),
		VerifyMedianMS:       median(verifyTimes),
		ProofBytes:           proofBytes,
		PublicWitnessBytes:   publicBuffer.Len(),
		GoVersion:            runtime.Version(),
		GOOS:                 runtime.GOOS,
		GOARCH:               runtime.GOARCH,
		GnarkVersion:         "v0.14.0",
		Backend:              "Groth16",
		Curve:                "BN254",
		CoordinateConvention: "inclusive quantized integer boxes",
		GeometryBackend:      *geometry,
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		panic(err)
	}
	fmt.Println(string(encoded))
	if *output != "" {
		if err := os.WriteFile(*output, append(encoded, '\n'), 0o644); err != nil {
			panic(err)
		}
	}
}
