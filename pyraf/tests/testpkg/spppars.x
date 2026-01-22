task simplepars, psetpars0, psetpars1

procedure simplepars()

char    strpar[SZ_LINE]
int     intpar, clgeti()
real    fltpar, clgetr()
bool    boolpar, clgetb()

begin
    call clgstr ("strpar", strpar, SZ_LINE)
    intpar  = clgeti ("intpar")
    fltpar  = clgetr ("fltpar")
    boolpar = clgetb ("boolpar")

    call printf ("strpar=%s\n")
        call pargstr (strpar)
    
    call printf ("intpar=%d\n")
        call pargi (intpar)

    call printf ("fltpar=%g\n")
        call pargr (fltpar)

    call printf ("boolpar=%b\n")
        call pargb (boolpar)

end


# Simplified access to a parameter set: directly call for the
# parameters within the parameter set by their name
procedure psetpars0()

char    psstrpar[SZ_LINE]
int     psintpar, clgeti()

begin

    call clgstr ("psstrpar", psstrpar, SZ_LINE)
    psintpar = clgeti ("psintpar")

    call printf ("psstrpar=%s\n")
        call pargstr (psstrpar)

    call printf ("psintpar=%d\n")
        call pargi (psintpar)

end

# Official access to a prameter set: open the parameter set and access the
# parameters from the opened set
procedure psetpars1()

char    psstrpar[SZ_LINE]
int     psintpar, clgpseti()
pointer psetpar, clopset()

begin

    psetpar = clopset("psetpar")
    call clgpset (psetpar, "psstrpar", psstrpar, SZ_LINE)
    psintpar = clgpseti (psetpar, "psintpar")
    call clcpset(psetpar)

    call printf ("psstrpar=%s\n")
        call pargstr (psstrpar)

    call printf ("psintpar=%d\n")
        call pargi (psintpar)

end
