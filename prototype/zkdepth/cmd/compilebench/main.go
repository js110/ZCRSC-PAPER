// compilebench measures complete signed-box circuit compilation, not proving.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
	"os"
	zkdepth "pcvcs-paper-a/zkdepth"
	"runtime"
	"time"
)

func main() {
	n := flag.Int("n", 4, "issuer count")
	d := flag.Int("d", 2, "dimension")
	k := flag.Int("k", 3, "subset threshold; depth keeps public threshold")
	backend := flag.String("backend", "subset", "subset or depth")
	flag.Parse()
	if *n < 2 || *d < 1 || *k < 1 || *k > *n || (*backend != "depth" && *backend != "subset") {
		fmt.Fprintln(os.Stderr, "invalid parameters")
		os.Exit(2)
	}
	c := zkdepth.NewCircuit(*n, *d, 16)
	if *backend == "subset" {
		c.SubsetThreshold = *k
	}
	start := time.Now()
	cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, c)
	if err != nil {
		panic(err)
	}
	result := map[string]interface{}{"n": *n, "d": *d, "k": *k, "backend": *backend,
		"constraints": cs.GetNbConstraints(), "compile_ms": float64(time.Since(start).Microseconds()) / 1000,
		"go_version": runtime.Version(), "goos": runtime.GOOS, "goarch": runtime.GOARCH, "bits": 16}
	data, err := json.Marshal(result)
	if err != nil {
		panic(err)
	}
	fmt.Println("RESULT_JSON:" + string(data))
}
