pragma circom 2.0.0;
include "node_modules/circomlib/circuits/comparators.circom";

template IdentityProof() {
    // PRIVATE INPUTS
    signal input private_nik_hash;
    signal input private_name_hash;
    signal input private_birth_year; // YYYY

    // PUBLIC INPUTS
    signal input public_nik_hash;
    signal input public_name_hash;
    signal input public_birth_year; // YYYY
  
    private_nik_hash === public_nik_hash;
    private_name_hash === public_name_hash;
    private_birth_year === public_birth_year;
   
    signal output out_dummy; 
    out_dummy <== 1; // Index 0 dummy

    signal output out_nik_hash;
    out_nik_hash <== public_nik_hash; // Index 1
    
    signal output out_name_hash;
    out_name_hash <== public_name_hash; // Index 2

    signal output out_birth_year;
    out_birth_year <== public_birth_year; // Index 3
 
}

component main = IdentityProof();