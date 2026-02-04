# Procedure clpars: CL script to just print the parameters
procedure clpars(strpar, intpar, fltpar, boolpar, psetpar)
begin
    print ("strpar=", strpar)
    print ("intpar=", intpar)
    print ("fltpar=", fltpar)
    print ("boolpar=", boolpar)
    print ("psstrpar=", psetpar.psstrpar)
    print ("psintpar=", psetpar.psintpar)
end
