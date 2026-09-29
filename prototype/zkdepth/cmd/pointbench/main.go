package main

import (
    "bytes"
    "encoding/json"
    "flag"
    "fmt"
    "os"

    "github.com/consensys/gnark-crypto/ecc"
    "github.com/consensys/gnark/backend/groth16"
    "github.com/consensys/gnark/frontend"
    "github.com/consensys/gnark/frontend/cs/r1cs"

    zkdepth "pcvcs-paper-a/zkdepth"
)

type result struct {
    D int `json:"d"`
    Bits int `json:"bits"`
    Constraints int `json:"constraints"`
    ProofBytes int `json:"proof_bytes"`
    PublicWitnessBytes int `json:"public_witness_bytes"`
    Baseline string `json:"baseline"`
    Note string `json:"note"`
}

func main() {
    d := flag.Int("d", 3, "point dimension")
    bits := flag.Int("bits", 16, "coordinate bit width")
    output := flag.String("output", "", "optional JSON output path")
    flag.Parse()

    shape := zkdepth.NewPointCircuit(*d, *bits)
    ccs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, shape)
    if err != nil { panic(err) }
    pk, vk, err := groth16.Setup(ccs)
    if err != nil { panic(err) }
    assignment := zkdepth.NewPointAssignment(*d, *bits)
    witness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
    if err != nil { panic(err) }
    publicWitness, err := witness.Public()
    if err != nil { panic(err) }
    proof, err := groth16.Prove(ccs, pk, witness)
    if err != nil { panic(err) }
    if err := groth16.Verify(proof, vk, publicWitness); err != nil { panic(err) }

    var proofBuffer, publicBuffer bytes.Buffer
    if _, err := proof.WriteTo(&proofBuffer); err != nil { panic(err) }
    if _, err := publicWitness.WriteTo(&publicBuffer); err != nil { panic(err) }

    out := result{
        D:*d, Bits:*bits, Constraints:ccs.GetNbConstraints(),
        ProofBytes:proofBuffer.Len(), PublicWitnessBytes:publicBuffer.Len(),
        Baseline:"private point-in-policy Groth16",
        Note:"Lower-bound predicate only; no issuer signatures, uncertainty boxes, or Byzantine robustness.",
    }
    encoded, err := json.MarshalIndent(out, "", "  ")
    if err != nil { panic(err) }
    fmt.Println(string(encoded))
    if *output != "" {
        if err := os.WriteFile(*output, append(encoded,'\n'), 0o644); err != nil { panic(err) }
    }
}
