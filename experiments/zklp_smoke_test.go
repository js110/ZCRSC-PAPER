// Instrumentation overlay for the unmodified, pinned upstream test circuit.
// Installed in upstream loc2index32 by run_same_runner.py; no upstream code is vendored.
package loc2index64

import (
	"bufio"
	"bytes"
	"encoding/json"
	"math/big"
	"os"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

func TestPaperSameRunnerZKLP(t *testing.T) {
	output := os.Getenv("ZCRSC_BENCH_OUTPUT")
	if output == "" {
		t.Fatal("ZCRSC_BENCH_OUTPUT is required")
	}
	repetitions, err := strconv.Atoi(os.Getenv("ZCRSC_BENCH_REPETITIONS"))
	if err != nil || repetitions < 1 {
		t.Fatal("positive ZCRSC_BENCH_REPETITIONS is required")
	}
	f, err := os.Open("../data/f32/loc2index32.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	if !scanner.Scan() {
		t.Fatal("missing first upstream test vector")
	}
	fields := strings.Fields(scanner.Text())
	if len(fields) != 6 {
		t.Fatal("unexpected upstream vector format")
	}
	values := make([]*big.Int, 6)
	for i, field := range fields {
		var ok bool
		values[i], ok = new(big.Int).SetString(field, 16)
		if !ok {
			t.Fatal("invalid upstream hexadecimal vector")
		}
	}
	ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, &loc2Index32Circuit{})
	if err != nil {
		t.Fatal(err)
	}
	started := time.Now()
	pk, vk, err := groth16.Setup(ccs)
	if err != nil {
		t.Fatal(err)
	}
	setupMS := float64(time.Since(started).Microseconds()) / 1000
	assignment := &loc2Index32Circuit{Lat: values[0], Lng: values[1], Resolution: values[2], I: values[3], J: values[4], K: values[5]}
	witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
	if err != nil {
		t.Fatal(err)
	}
	public, err := witness.Public()
	if err != nil {
		t.Fatal(err)
	}
	proves, verifies := []float64{}, []float64{}
	var proofBuffer, publicBuffer bytes.Buffer
	for i := 0; i < repetitions; i++ {
		started = time.Now()
		proof, e := groth16.Prove(ccs, pk, witness)
		if e != nil {
			t.Fatal(e)
		}
		proves = append(proves, float64(time.Since(started).Microseconds())/1000)
		started = time.Now()
		if e = groth16.Verify(proof, vk, public); e != nil {
			t.Fatal(e)
		}
		verifies = append(verifies, float64(time.Since(started).Microseconds())/1000)
		if i == 0 {
			if _, e = proof.WriteTo(&proofBuffer); e != nil {
				t.Fatal(e)
			}
		}
	}
	if _, err = public.WriteTo(&publicBuffer); err != nil {
		t.Fatal(err)
	}
	result := map[string]interface{}{"n": 1, "d": 2, "constraints": ccs.GetNbConstraints(), "repetitions": repetitions, "setup_ms": setupMS,
		"prove_ms": proves, "verify_ms": verifies, "proof_bytes": proofBuffer.Len(), "public_witness_bytes": publicBuffer.Len(),
		"go_version": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "backend": "Groth16", "curve": "BN254",
		"upstream_commit": "e8e321524982ddd9dddea37db6fa352529db62c4", "test_vector_hex": fields,
		"relation": "upstream loc2Index32Circuit over the first vector; instrumentation only"}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(output, append(encoded, '\n'), 0644); err != nil {
		t.Fatal(err)
	}
}
