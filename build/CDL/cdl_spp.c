#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#define  CDL_LIBRARY_SOURCE
#include "cdl.h"

/*
 *  CDL_SPP.H  -- Header file for the CDL SPP interface.  Fortran compilers
 *  on various platforms may append one or more trailing underscores to 
 *  symbol names, we'll use macros for the interface names and use defines
 *  to see what the symbol name is.
 */

#include "cdl_f77.h"

#ifdef _NO_US_

#define	CDS_OPEN		cdopen
#define	CDS_DISPLAYPIX		cdsppx
#define	CDS_READCURSOR		crdcur
#define	CDS_SETCURSOR		cscurs
#define	CDS_CLEARFRAME		cclfrm
#define	CDS_SELECTFB		cselfb
#define	CDS_CLOSE		cclose
#define	CDS_DISPLAYIRAF		cdspir
#define	CDS_ISIRAF		cisirf
#define	CDS_READIRAF		crdirf
#define	CDS_DISPLAYFITS		cdspft
#define	CDS_ISFITS		cisfts
#define	CDS_READFITS		crdfts
#define	CDS_COMPZSCALE		ccmpzs
#define	CDS_ZSCALEIMAGE		czscim
#define	CDS_PRINTPIX		cprpix
#define	CDS_PRINTPIXTOFILE	cprpfl
#define	CDS_READIMAGE		crdimg
#define	CDS_READFRAMEBUFFER	crdfrb
#define	CDS_READSUBRAS		crsubr
#define	CDS_WRITESUBRAS		cwsubr
#define	CDS_SETWCS		cstwcs
#define	CDS_SETFBCONFIG		csfbcf
#define	CDS_GETFBCONFIG		cgfbcf
#define	CDS_LOOKUPFBSIZE	clkfbs
#define	CDS_SETFRAME		csfram
#define	CDS_SETZTRANS		csztrn
#define	CDS_SETZSCALE		cszscl
#define	CDS_SETSAMPLE		cssamp
#define	CDS_SETSAMPLELINES	cssaml
#define	CDS_SETCONTRAST		cscntr
#define	CDS_SETNAME		csname
#define	CDS_SETTITLE		cstitl
#define	CDS_GETWCS		cgtwcs
#define	CDS_GETFRAME		cgfram
#define	CDS_GETZTRANS		cgztrn
#define	CDS_GETZSCALE		cgzscl
#define	CDS_GETSAMPLE		cgsamp
#define	CDS_GETSAMPLELINES	cgsmpl
#define	CDS_GETCONTRAST		cgcntr
#define	CDS_GETNAME		cgname
#define	CDS_GETTITLE		cgtitl
#define	CDS_MAPFRAME		cmapfr
#define	CDS_MARKCOORDSFILE	cmkcfl
#define	CDS_MARKPOINT		cmkpnt
#define	CDS_MARKPOINTLABEL	cmkpnl
#define	CDS_MARKLINE		cmklin
#define	CDS_MARKBOX		cmkbox
#define	CDS_MARKPOLYLINE	cmkpln
#define	CDS_MARKPOLYGON		cmkpgn
#define	CDS_MARKCIRCLE		cmkcrc
#define	CDS_MARKCIRCANNULI	cmkcan
#define	CDS_MARKELLIPSE		cmkell
#define	CDS_MARKELLIPANNULI	cmkela
#define	CDS_MARKTEXT		cmktxt
#define	CDS_SETFONT		csfont
#define	CDS_SETLINEWIDTH	cslwid
#define	CDS_SETLINESTYLE	cslsty
#define	CDS_SETTEXTWIDTH	cstwid
#define	CDS_DELETEMARK		cdelmk
#define	CDS_CLEAROVERLAY	cclrov
#define	CDS_REDRAWOVERLAY	crdrov
#define	CDS_SETDEBUG		cstdbg

#else

#define	CDS_OPEN		cdopen_
#define	CDS_DISPLAYPIX		cdsppx_
#define	CDS_READCURSOR		crdcur_
#define	CDS_SETCURSOR		cscurs_
#define	CDS_CLEARFRAME		cclfrm_
#define	CDS_SELECTFB		cselfb_
#define	CDS_CLOSE		cclose_
#define	CDS_DISPLAYIRAF		cdspir_
#define	CDS_ISIRAF		cisirf_
#define	CDS_READIRAF		crdirf_
#define	CDS_DISPLAYFITS		cdspft_
#define	CDS_ISFITS		cisfts_
#define	CDS_READFITS		crdfts_
#define	CDS_COMPZSCALE		ccmpzs_
#define	CDS_ZSCALEIMAGE		czscim_
#define	CDS_PRINTPIX		cprpix_
#define	CDS_PRINTPIXTOFILE	cprpfl_
#define	CDS_READIMAGE		crdimg_
#define	CDS_READFRAMEBUFFER	crdfrb_
#define	CDS_READSUBRAS		crsubr_
#define	CDS_WRITESUBRAS		cwsubr_
#define	CDS_SETWCS		cstwcs_
#define	CDS_SETFBCONFIG		csfbcf_
#define	CDS_GETFBCONFIG		cgfbcf_
#define	CDS_LOOKUPFBSIZE	clkfbs_
#define	CDS_SETFRAME		csfram_
#define	CDS_SETZTRANS		csztrn_
#define	CDS_SETZSCALE		cszscl_
#define	CDS_SETSAMPLE		cssamp_
#define	CDS_SETSAMPLELINES	cssaml_
#define	CDS_SETCONTRAST		cscntr_
#define	CDS_SETNAME		csname_
#define	CDS_SETTITLE		cstitl_
#define	CDS_GETWCS		cgtwcs_
#define	CDS_GETFRAME		cgfram_
#define	CDS_GETZTRANS		cgztrn_
#define	CDS_GETZSCALE		cgzscl_
#define	CDS_GETSAMPLE		cgsamp_
#define	CDS_GETSAMPLELINES	cgsmpl_
#define	CDS_GETCONTRAST		cgcntr_
#define	CDS_GETNAME		cgname_
#define	CDS_GETTITLE		cgtitl_
#define	CDS_MAPFRAME		cmapfr_
#define	CDS_MARKCOORDSFILE	cmkcfl_
#define	CDS_MARKPOINT		cmkpnt_
#define	CDS_MARKPOINTLABEL	cmkpnl_
#define	CDS_MARKLINE		cmklin_
#define	CDS_MARKBOX		cmkbox_
#define	CDS_MARKPOLYLINE	cmkpln_
#define	CDS_MARKPOLYGON		cmkpgn_
#define	CDS_MARKCIRCLE		cmkcrc_
#define	CDS_MARKCIRCANNULI	cmkcan_
#define	CDS_MARKELLIPSE		cmkell_
#define	CDS_MARKELLIPANNULI	cmkela_
#define	CDS_MARKTEXT		cmktxt_
#define	CDS_SETFONT		csfont_
#define	CDS_SETLINEWIDTH	cslwid_
#define	CDS_SETLINESTYLE	cslsty_
#define	CDS_SETTEXTWIDTH	cstwid_
#define	CDS_DELETEMARK		cdelmk_
#define	CDS_CLEAROVERLAY	cclrov_
#define	CDS_REDRAWOVERLAY	crdrov_
#define	CDS_SETDEBUG		cstdbg_

#endif


#ifdef ANSI_FUNC

void CDS_OPEN(char *imtdev, int *ier);
void CDS_DISPLAYPIX(uchar *pix, int *nx, int *ny, int *bitpix, int *frame, int *fbconfig, int *zscale, int *ier);
void CDS_READCURSOR(int *sample, float *x, float *y, int *wcs, char *key, int *ier);
void CDS_DISPLAYIRAF(char *fname, int *band, int *frame, int *fbconfig, int *zscale, int *ier);
void CDS_ISIRAF(char *fname, int *isiraf);
void CDS_READIRAF(char *fname, int *band, uchar *pix, int *nx, int *ny, int *bitpix, char *title, int *ier);
void CDS_DISPLAYFITS(char *fname, int *frame, int *fbconfig, int *zscale, int *ier);
void CDS_ISFITS(char *fname, int *isfits);
void CDS_READFITS(char *fname, uchar *pix, int *nx, int *ny, int *bitpix, char *title, int *ier);
void CDS_SETCURSOR(int *x, int *y, int *wcs, int *ier);
void CDS_SETWCS(char *name, char *title, float *a, float *b, float *c, float *d, float *tx, float *ty, float *z1, float *z2, int *zt, int *ier);
void CDS_GETWCS(char *name, char *title, float *a, float *b, float *c, float *d, float *tx, float *ty, float *z1, float *z2, int *zt, int *ier);
void CDS_CLEARFRAME(int *ier);
void CDS_SELECTFB(int *nx, int *ny, int *fb, int *w, int *h, int *nf, int *reset);
void CDS_CLOSE(void);
void CDS_READIMAGE(uchar *pix, int *nx, int *ny, int *ier);
void CDS_READFRAMEBUFFER(uchar *pix, int *nx, int *ny, int *ier);
void CDS_COMPZSCALE(uchar *pix, int *nx, int *ny, int *bitpix, float *z1, float *z2);
void CDS_ZSCALEIMAGE(uchar *pix, int *nx, int *ny, int *bitpix, float *z1, float *z2);
void CDS_PRINTPIX(char *cmd, uchar *pix, int *nx, int *ny, int *annotate, int *ier);
void CDS_PRINTPIXTOFILE(char *fname, uchar *pix, int *nx, int *ny, int *annotate, int *ier);
void CDS_READSUBRAS(int *lx, int *ly, int *nx, int *ny, uchar *pix, int *ier);
void CDS_WRITESUBRAS(int *lx, int *ly, int *nx, int *ny, uchar *pix, int *ier);
void CDS_SETFBCONFIG(int *configno);
void CDS_GETFBCONFIG(int *configno, int *w, int *h, int *nframes);
void CDS_LOOKUPFBSIZE(int *configno, int *w, int *h, int *nf);
void CDS_SETFRAME(int *frame);
void CDS_SETZTRANS(int *ztrans);
void CDS_SETZSCALE(float *z1, float *z2);
void CDS_SETSAMPLE(int *nsample);
void CDS_SETSAMPLELINES(int *nlines);
void CDS_SETCONTRAST(float *contrast);
void CDS_SETNAME(char *imname);
void CDS_SETTITLE(char *imtitle);
void CDS_GETFRAME(int *frame);
void CDS_GETZTRANS(int *ztrans);
void CDS_GETZSCALE(float *z1, float *z2);
void CDS_GETSAMPLE(int *nsample);
void CDS_GETSAMPLELINES(int *nlines);
void CDS_GETCONTRAST(float *contrast);
void CDS_GETNAME(char *imname);
void CDS_GETTITLE(char *imtitle);
void CDS_MAPFRAME(int *frame, int *ier);
void CDS_MARKCOORDSFILE(char *fname, int *type, int *size, int *color, int *label, int *ier);
void CDS_MARKPOINT(int *x, int *y, int *number, int *size, int *type, int *color, int *ier);
void CDS_MARKPOINTLABEL(int *x, int *y, char *label, int *size, int *type, int *color, int *ier);
void CDS_MARKLINE(int *xs, int *ys, int *xe, int *ye, int *color, int *ier);
void CDS_MARKBOX(int *lx, int *ly, int *ux, int *uy, int *fill, int *color, int *ier);
void CDS_MARKPOLYGON(int *xarray, int *yarray, int *npts, int *fill, int *color, int *ier);
void CDS_MARKPOLYLINE(int *xarray, int *yarray, int *npts, int *color, int *ier);
void CDS_MARKCIRCLE(int *x, int *y, int *radius, int *fill, int *color, int *ier);
void CDS_MARKCIRCANNULI(int *x, int *y, int *radius, int *nannuli, int *sep, int *color, int *ier);
void CDS_MARKELLIPSE(int *x, int *y, int *xrad, int *yrad, float *ang, int *fill, int *color, int *ier);
void CDS_MARKELLIPANNULI(int *x, int *y, int *xrad, int *yrad, float *ang, int *nannuli, int *sep, int *color, int *ier);
void CDS_MARKTEXT(int *x, int *y, char *str, float *size, float *angle, int *color, int *ier);
void CDS_SETFONT(int *font);
void CDS_SETLINEWIDTH(int *width);
void CDS_SETLINESTYLE(int *style);
void CDS_SETTEXTWIDTH(int *width);
void CDS_DELETEMARK(int *x, int *y, int *ier);
void CDS_CLEAROVERLAY(int *ier);
void CDS_REDRAWOVERLAY(int *ier);
void CDS_SETDEBUG(int *state);
static void strupk(char *str, char *outstr, int maxch);
static void strpak(char *sppstr, char *cstr, int maxch);

#else

/* Function Definitions. */
void    CDS_OPEN();
void    CDS_DISPLAYPIX(), CDS_DISPLAYIRAF(), CDS_DISPLAYFITS();
void    CDS_READIRAF(), CDS_READFITS(), CDS_CLEARFRAME();
void    CDS_READIMAGE(), CDS_READFRAMEBUFFER(), CDS_READSUBRAS();
void    CDS_WRITESUBRAS(), CDS_SETCURSOR(), CDS_READCURSOR();
void    CDS_SELECTFB(), CDS_CLOSE(), CDS_COMPZSCALE(), CDS_ZSCALEIMAGE();
void    CDS_SETFRAME(), CDS_SETFBCONFIG(), CDS_SETZTRANS(), CDS_SETZOOM();
void    CDS_SETSAMPLE(), CDS_SETCONTRAST(), CDS_SETNAME(), CDS_SETTITLE();
void    CDS_GETFRAME(), CDS_GETFBCONFIG(), CDS_GETZTRANS(), CDS_GETZOOM();
void    CDS_GETSAMPLE(), CDS_GETCONTRAST(), CDS_GETNAME(), CDS_GETTITLE();
void    CDS_SETZSCALE(), CDS_GETZSCALE(), CDS_LOOKUPFBSIZE();
void    CDS_ISIRAF(), CDS_ISFITS(), CDS_SETDEBUG();
void    CDS_PRINTPIX (), CDS_PRINTPIXTOFILE ();
void    CDS_SETSAMPLELINES (), CDS_GETSAMPLELINES ();
void    CDS_SETWCS(), CDS_GETWCS();

/* Marker Function Definitions. */
void    CDS_MARKPOINT(), CDS_MARKLINE(), CDS_MARKBOX(), CDS_MARKPOLYLINE();
void    CDS_MARKPOLYGON(), CDS_MARKCIRCLE(), CDS_MARKCIRCANNULI();
void    CDS_MARKELLIPSE(), CDS_MARKELLIPANNULI(), CDS_MARKTEXT();
void    CDS_DELETEMARK(), CDS_CLEAROVERLAY(), CDS_REDRAWOVERLAY();
void    CDS_SETFONT(), CDS_SETLINEWIDTH(), CDS_SETTEXTWIDTH();
void    CDS_SETLINESTYLE(), CDS_MARKCOORDSFILE(), CDS_MARKPOINTLABEL();

static void	strupk(), strpak();

#endif



/*  
 *  CDL_SPP.C -- SPP binding for the CDL package.  Even though we mostly
 *  call the F77 routines here we need a unique procedure for each function
 *  so we can map the SPP symbol names correctly.
 */

char    cstr[512], cstr2[512];


/*  CDS_OPEN -- Open and initialize the CDL package.  */

#ifdef ANSI_FUNC

void 
CDS_OPEN (
    char *imtdev,                       /* connection device	*/
    int *ier				/* error code		*/
)
#else

void
CDS_OPEN (imtdev, ier)
char	*imtdev;                        /* connection device	*/
int	*ier;				/* error code		*/
#endif
{
        strpak (imtdev, cstr, SZ_FNAME);
        CDF_OPEN (cstr, ier, strlen(cstr));
}


/*  CDS_DISPLAYPIX -- Display a raw pixel array to the server.  */

#ifdef ANSI_FUNC

void 
CDS_DISPLAYPIX (
    uchar *pix,				/* pixels to display	*/
    int *nx,
    int *ny,				/* image dimensions	*/
    int *bitpix,			/* pixel size		*/
    int *frame,				/* display frame	*/
    int *fbconfig,			/* FB config number	*/
    int *zscale,			/* do zscale of image?	*/
    int *ier				/* error code		*/
)
#else

void
CDS_DISPLAYPIX (pix, nx, ny, bitpix, frame, fbconfig, zscale, ier)
uchar	*pix;				/* pixels to display	*/
int	*nx, *ny;			/* image dimensions	*/
int	*bitpix;			/* pixel size		*/
int	*frame;				/* display frame	*/
int	*fbconfig;			/* FB config number	*/
int	*zscale;			/* do zscale of image?	*/
int	*ier;				/* error code		*/
#endif
{
	CDF_DISPLAYPIX (pix, nx, ny, bitpix, frame, fbconfig, zscale, ier);
} 
 

/*  CDS_READCURSOR --  Read the current cursor position. */

#ifdef ANSI_FUNC

void 
CDS_READCURSOR (
    int *sample,                 	/* wait for keystroke?  */
    float *x,
    float *y,                 		/* position (output)	*/
    int *wcs,				/* WCS			*/
    char *key,                   	/* keystroke (output)	*/
    int *ier				/* error code		*/
)
#else

void
CDS_READCURSOR (sample, x, y, wcs, key, ier)
int     *sample;                 	/* wait for keystroke?  */
float   *x, *y;                 	/* position (output)	*/
int 	*wcs;				/* WCS			*/
char    *key;                   	/* keystroke (output)	*/
int	*ier;				/* error code		*/
#endif
{
	char	ch[2];
	CDF_READCURSOR (sample, x, y, wcs, ch, ier);
	strupk (ch, key, 2);

	/* If the char read is a control char, return EOS */
	if (iscntrl(key[0]))
	    key[0] = key[1] = '\0';
} 


/*  CDS_DISPLAYIRAF -- Display an IRAF OIF format image.  */

#ifdef ANSI_FUNC

void 
CDS_DISPLAYIRAF (
    char *fname,			/* image name		*/
    int *band,				/* image band if 3-d	*/
    int *frame,				/* display frame	*/
    int *fbconfig,			/* frame buffer config	*/
    int *zscale,			/* do zscale of image?	*/
    int *ier				/* error code		*/
)
#else

void
CDS_DISPLAYIRAF (fname, band, frame, fbconfig, zscale, ier)
char	*fname;				/* image name		*/
int	*band;				/* image band if 3-d	*/
int	*frame;				/* display frame	*/
int	*fbconfig;			/* frame buffer config	*/
int	*zscale;			/* do zscale of image?	*/
int	*ier;				/* error code		*/
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_DISPLAYIRAF (cstr, band, frame, fbconfig, zscale, ier, SZ_FNAME);
}


/* CDS_ISIRAF -- Test a file to see if it is a IRAF file.  */

#ifdef ANSI_FUNC

void 
CDS_ISIRAF (
    char *fname,			/* input filename 	*/
    int *isiraf
)
#else

void 
CDS_ISIRAF (fname, isiraf)
char	*fname;				/* input filename 	*/
int	*isiraf;
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_ISIRAF (cstr, isiraf, SZ_FNAME);
}


/*  CDS_READIRAF -- Read the pixels from an IRAF OIF format image.  */

#ifdef ANSI_FUNC

void 
CDS_READIRAF (
    char *fname,			/* image name		*/
    int *band,				/* image band if 3-d	*/
    uchar *pix,				/* pixel array (output) */
    int *nx,
    int *ny,				/* dimensions (output)	*/
    int *bitpix,			/* pixel size (output)	*/
    char *title,			/* image title (output) */
    int *ier				/* error code		*/
)
#else

void
CDS_READIRAF (fname, band, pix, nx, ny, bitpix, title, ier)
char	*fname;				/* image name		*/
int	*band;				/* image band if 3-d	*/
uchar	*pix;				/* pixel array (output) */
int	*nx, *ny;			/* dimensions (output)	*/
int	*bitpix;			/* pixel size (output)	*/
char	*title;				/* image title (output) */
int	*ier;				/* error code		*/
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_READIRAF (cstr, band, pix, nx, ny, bitpix, cstr2, ier, SZ_FNAME);
	strupk (cstr2, title, SZ_FNAME);
}


/*  CDS_DISPLAYFITS -- Display a simple FITS format image.  */

#ifdef ANSI_FUNC

void 
CDS_DISPLAYFITS (
    char *fname,
    int *frame,
    int *fbconfig,
    int *zscale,
    int *ier				/* error code		*/
)
#else

void
CDS_DISPLAYFITS (fname, frame, fbconfig, zscale, ier)
char	*fname;
int	*frame;
int	*fbconfig;
int	*zscale;
int	*ier;				/* error code		*/
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_DISPLAYFITS (cstr, frame, fbconfig, zscale, ier, SZ_FNAME);
}


/*  CDS_ISFITS -- Test a file to see if it is a simple FITS file.  */

#ifdef ANSI_FUNC

void 
CDS_ISFITS (
    char *fname,			/* input filename 	*/
    int *isfits				/* return value		*/
)
#else

void 
CDS_ISFITS (fname, isfits)
char	*fname;				/* input filename 	*/
int	*isfits;			/* return value		*/
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_ISFITS (cstr, isfits, SZ_FNAME);
}


/*  CDS_READFITS -- Read the pixels from a simple FITS format image.  */

#ifdef ANSI_FUNC

void 
CDS_READFITS (
    char *fname,			/* image name		*/
    uchar *pix,				/* pixel array (output) */
    int *nx,
    int *ny,				/* dimensions (output)	*/
    int *bitpix,			/* pixel size (output)	*/
    char *title,			/* image title (output) */
    int *ier				/* error code		*/
)
#else

void
CDS_READFITS (fname, pix, nx, ny, bitpix, title, ier)
char	*fname;				/* image name		*/
uchar	*pix;				/* pixel array (output) */
int	*nx, *ny;			/* dimensions (output)	*/
int	*bitpix;			/* pixel size (output)	*/
char	*title;				/* image title (output) */
int	*ier;				/* error code		*/
#endif
{
        strpak (fname, cstr, SZ_FNAME);
	CDF_READFITS (fname, pix, nx, ny, bitpix, cstr2, ier, SZ_FNAME);
	strupk (cstr2, title, SZ_FNAME);
}


/*  CDS_SETCURSOR --  Set the current logical cursor position.  */

#ifdef ANSI_FUNC

void 
CDS_SETCURSOR (
    int *x,
    int *y,                 		/* position 		*/
    int *wcs,                   	/* cursor wcs		*/
    int *ier				/* error code		*/
)
#else

void
CDS_SETCURSOR (x, y, wcs, ier)
int   	*x, *y;                 	/* position 		*/
int     *wcs;                   	/* cursor wcs		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_SETCURSOR (x, y, wcs, ier);
} 


/*  CDS_SETWCS --  Set the WCS of the screen.  */

#ifdef ANSI_FUNC

void 
CDS_SETWCS (
    char *name,                  	/* name string          */
    char *title,                 	/* title string         */
    float *a,
    float *b,
    float *c,
    float *d,             		/* WCS values           */
    float *tx,
    float *ty,                 		/* translation          */
    float *z1,
    float *z2,                 		/* zscale values        */
    int *zt,                     	/* transformation type  */
    int *ier				/* error code		*/
)
#else

void
CDS_SETWCS (name, title, a, b, c, d, tx, ty, z1, z2, zt, ier)
char    *name;                  	/* name string          */
char    *title;                 	/* title string         */
float   *a, *b, *c, *d;             	/* WCS values           */
float   *tx, *ty;                 	/* translation          */
float   *z1, *z2;                 	/* zscale values        */
int     *zt;                     	/* transformation type  */
int	*ier;				/* error code		*/
#endif
{
        strpak (name, cstr, SZ_FNAME);
        strpak (title, cstr2, SZ_FNAME);
	CDF_SETWCS (cstr, cstr2, a, b, c, d, tx,ty, z1,z2, zt, ier, 
	    SZ_FNAME, SZ_FNAME);
} 


/*  CDS_GETWCS -- Get the current display frame WCS information.  */

#ifdef ANSI_FUNC

void 
CDS_GETWCS (
    char *name,                  	/* name string          */
    char *title,                 	/* title string         */
    float *a,
    float *b,
    float *c,
    float *d,         			/* WCS values           */
    float *tx,
    float *ty,               		/* translation          */
    float *z1,
    float *z2,               		/* zscale values        */
    int *zt,                    	/* transformation type  */
    int *ier				/* error code		*/
)
#else

void
CDS_GETWCS (name, title, a, b, c, d, tx, ty, z1, z2, zt, ier)
char    *name;                  	/* name string          */
char    *title;                 	/* title string         */
float   *a, *b, *c, *d;         	/* WCS values           */
float   *tx, *ty;               	/* translation          */
float   *z1, *z2;               	/* zscale values        */
int     *zt;                    	/* transformation type  */
int	*ier;				/* error code		*/
#endif
{
	CDF_GETWCS (cstr, cstr2, a, b, c, d, tx,ty, z1,z2, zt, ier, 
	    SZ_FNAME, SZ_FNAME);
        strupk (cstr, name, SZ_FNAME);
        strupk (cstr2, title, SZ_FNAME);
} 


/*  CDS_CLEARFRAME -- Erase the current display frame.  */

#ifdef ANSI_FUNC

void 
CDS_CLEARFRAME (
    int *ier				/* error code		*/
)
#else

void
CDS_CLEARFRAME (ier)
int	*ier;				/* error code		*/
#endif
{
	CDF_CLEARFRAME (ier);
} 


/*  CDS_SELECTFB -- Select an appropriate frame buffer for the image.  */

#ifdef ANSI_FUNC

void 
CDS_SELECTFB (
    int *nx,
    int *ny,				/* image size		*/
    int *fb,				/* frame buffer		*/
    int *w,
    int *h,				/* frame size		*/
    int *nf,				/* number of frames	*/
    int *reset				/* reset after select	*/
)
#else

void
CDS_SELECTFB (nx, ny, fb, w, h, nf, reset)
int	*nx, *ny;			/* image size		*/
int	*fb;				/* frame buffer		*/
int	*w, *h;				/* frame size		*/
int	*nf;				/* number of frames	*/
int	*reset;				/* reset after select	*/
#endif
{
	CDF_SELECTFB (nx, ny, fb, w, h, nf, reset);
} 


/*  CDS_CLOSE -- Close the CDL package descriptor.  */

#ifdef ANSI_FUNC

void 
CDS_CLOSE (void)
#else

void
CDS_CLOSE ()
#endif
{
	CDF_CLOSE ();
} 


/*  CDS_READIMAGE -- Read the currently displayed image.  */

#ifdef ANSI_FUNC

void 
CDS_READIMAGE (
    uchar *pix,                   	/* image pixels (output)*/
    int *nx,
    int *ny,               		/* dimensions (output)  */
    int *ier				/* error code		*/
)
#else

void
CDS_READIMAGE (pix, nx, ny, ier)
uchar   *pix;                   	/* image pixels (output)*/
int     *nx, *ny;               	/* dimensions (output)  */
int	*ier;				/* error code		*/
#endif
{
	CDF_READIMAGE (pix, nx, ny, ier);
} 


/*  CDS_READFRAMEBUFFER -- Read the contents of the entire frame buffer.  */

#ifdef ANSI_FUNC

void 
CDS_READFRAMEBUFFER (
    uchar *pix,                   	/* image pixels (output)*/
    int *nx,
    int *ny,               		/* dimensions (output)  */
    int *ier				/* error code		*/
)
#else

void
CDS_READFRAMEBUFFER (pix, nx, ny, ier)
uchar   *pix;                   	/* image pixels (output)*/
int     *nx, *ny;               	/* dimensions (output)  */
int	*ier;				/* error code		*/
#endif
{
	CDF_READFRAMEBUFFER (pix, nx, ny, ier);
} 


/*  CDS_COMPZSCALE -- Compute the optimal z1/z2 values for an array.  */

#ifdef ANSI_FUNC

void 
CDS_COMPZSCALE (
    uchar *pix,                   	/* data to be sampled   */
    int *nx,
    int *ny,                 		/* image dimensions     */
    int *bitpix,                 	/* bits per pixel       */
    float *z1,
    float *z2               		/* min/max zscale values*/
)
#else

void
CDS_COMPZSCALE (pix, nx, ny, bitpix, z1, z2)
uchar   *pix;                   	/* data to be sampled   */
int     *nx, *ny;                 	/* image dimensions     */
int     *bitpix;                 	/* bits per pixel       */
float   *z1, *z2;               	/* min/max zscale values*/
#endif
{
	CDF_COMPZSCALE (pix, nx, ny, bitpix, z1, z2);
} 


/*  CDS_ZSCALEIMAGE -- Compute the optimal z1/z2 values for an array.  */

#ifdef ANSI_FUNC

void 
CDS_ZSCALEIMAGE (
    uchar *pix,                   	/* data to be sampled   */
    int *nx,
    int *ny,                 		/* image dimensions     */
    int *bitpix,                 	/* bits per pixel       */
    float *z1,
    float *z2               		/* min/max zscale values*/
)
#else

void
CDS_ZSCALEIMAGE (pix, nx, ny, bitpix, z1, z2)
uchar   *pix;                   	/* data to be sampled   */
int     *nx, *ny;                 	/* image dimensions     */
int     *bitpix;                 	/* bits per pixel       */
float   *z1, *z2;               	/* min/max zscale values*/
#endif
{
	CDF_ZSCALEIMAGE (pix, nx, ny, bitpix, z1, z2);
} 


/*  CDS_PRINTPIX --  Print the given pixels as EPS to the named command. */

#ifdef ANSI_FUNC

void 
CDS_PRINTPIX (
    char *cmd,				/* command string	*/
    uchar *pix,				/* pixel array		*/
    int *nx,
    int *ny,				/* image dimensions	*/
    int *annotate,			/* annotate output?	*/
    int *ier				/* error code		*/
)
#else

void
CDS_PRINTPIX (cmd, pix, nx, ny, annotate, ier)
char	*cmd;				/* command string	*/
uchar	*pix;				/* pixel array		*/
int	*nx, *ny;			/* image dimensions	*/
int	*annotate;			/* annotate output?	*/
int	*ier;				/* error code		*/
#endif
{
        strpak (cmd, cstr, SZ_FNAME);
	CDF_PRINTPIX (cmd, pix, nx, ny, annotate, ier, SZ_FNAME);
} 


/*  CDS_PRINTPIXTOFILE -- Print the given pixels as EPS to the named file.  */

#ifdef ANSI_FUNC

void 
CDS_PRINTPIXTOFILE (
    char *fname,			/* filename		*/
    uchar *pix,				/* pixel array		*/
    int *nx,
    int *ny,				/* image dimensions	*/
    int *annotate,			/* annotate output?	*/
    int *ier				/* error code		*/
)
#else

void
CDS_PRINTPIXTOFILE (fname, pix, nx, ny, annotate, ier)
char	*fname;				/* filename		*/
uchar	*pix;				/* pixel array		*/
int	*nx, *ny;			/* image dimensions	*/
int	*annotate;			/* annotate output?	*/
int	*ier;				/* error code		*/
#endif
{
	strpak (fname, cstr, SZ_FNAME);
	CDF_PRINTPIXTOFILE (cstr, pix, nx, ny, annotate, ier, SZ_FNAME);
} 


/*  CDS_READSUBRAS -- Read a rectangular region of the frame buffer.  */

#ifdef ANSI_FUNC

void 
CDS_READSUBRAS (
    int *lx,
    int *ly,              		/* region corner        */
    int *nx,
    int *ny,                 		/* dimensions           */
    uchar *pix,                   	/* image pixels (output)*/
    int *ier				/* error code		*/
)
#else

void
CDS_READSUBRAS (lx, ly, nx, ny, pix, ier)
int     *lx, *ly;              		/* region corner        */
int     *nx, *ny;                 	/* dimensions           */
uchar   *pix;                   	/* image pixels (output)*/
int	*ier;				/* error code		*/
#endif
{
	CDF_READSUBRAS (lx, ly, nx, ny, pix, ier);
} 


/*  CDS_WRITESUBRAS -- Write a rectangular region of the frame buffer.  */

#ifdef ANSI_FUNC

void 
CDS_WRITESUBRAS (
    int *lx,
    int *ly,              		/* region corner        */
    int *nx,
    int *ny,                 		/* dimensions           */
    uchar *pix,                   	/* subraster pixels     */
    int *ier				/* error code		*/
)
#else

void
CDS_WRITESUBRAS (lx, ly, nx, ny, pix, ier)
int     *lx, *ly;              		/* region corner        */
int     *nx, *ny;                 	/* dimensions           */
uchar   *pix;                   	/* subraster pixels     */
int	*ier;				/* error code		*/
#endif
{
	CDF_WRITESUBRAS (lx, ly, nx, ny, pix, ier);
} 


/*  CDS_SETFBCONFIG -- Set the frame buffer configuration number.  */

#ifdef ANSI_FUNC

void 
CDS_SETFBCONFIG (
    int *configno			/* fb config number	*/
)
#else

void
CDS_SETFBCONFIG (configno)
int	*configno;			/* fb config number	*/
#endif
{
	CDF_SETFBCONFIG (configno);
} 


/*  CDS_GETFBCONFIG -- Get the frame buffer configuration number.  */

#ifdef ANSI_FUNC

void 
CDS_GETFBCONFIG (
    int *configno,                      /* fb config number     */
    int *w,
    int *h,                         	/* fb frame size        */
    int *nframes                        /* number of frames     */
)
#else

void
CDS_GETFBCONFIG (configno, w, h, nframes)
int     *configno;                      /* fb config number     */
int     *w, *h;                         /* fb frame size        */
int     *nframes;                       /* number of frames     */
#endif
{
	CDF_GETFBCONFIG (configno, w, h, nframes);
} 


/*  CDS_LOOKUPFBSIZE -- Lookup the frame buffer dimensions.*/

#ifdef ANSI_FUNC

void 
CDS_LOOKUPFBSIZE (
    int *configno,                      /* fb config number     */
    int *w,
    int *h,                         	/* fb frame size        */
    int *nf                             /* number of frames     */
)
#else

void
CDS_LOOKUPFBSIZE (configno, w, h, nf)
int     *configno;                      /* fb config number     */
int     *w, *h;                         /* fb frame size        */
int     *nf;                            /* number of frames     */
#endif
{
	CDF_LOOKUPFBSIZE (configno, w, h, nf);
}


/*  CDS_SETFRAME -- Set the current display frame.  */

#ifdef ANSI_FUNC

void 
CDS_SETFRAME (
    int *frame				/* frame number		*/
)
#else

void
CDS_SETFRAME (frame)
int	*frame;				/* frame number		*/
#endif
{
	CDF_SETFRAME (frame);
} 


/*  CDS_SETZTRANS -- Set the current zscale transform parameters.  */

#ifdef ANSI_FUNC

void 
CDS_SETZTRANS (
    int *ztrans				/* z-transform type	*/
)
#else

void
CDS_SETZTRANS (ztrans)
int	*ztrans;			/* z-transform type	*/
#endif
{
	CDF_SETZTRANS (ztrans);
} 


/*  CDS_SETZSCLAE -- Set the current zscale transform parameters.  */

#ifdef ANSI_FUNC

void 
CDS_SETZSCALE (
    float *z1,
    float *z2				/* zscale values	*/
)
#else

void
CDS_SETZSCALE (z1, z2)
float	*z1, *z2;			/* zscale values	*/
#endif
{
	CDF_SETZSCALE (z1, z2);
} 


/*  CDS_SETSAMPLE -- Set the number of zscale sample points to use.  */

#ifdef ANSI_FUNC

void 
CDS_SETSAMPLE (
    int *nsample			/* no. of sample pts	*/
)
#else

void
CDS_SETSAMPLE (nsample)
int	*nsample;			/* no. of sample pts	*/
#endif
{
	CDF_SETSAMPLE (nsample);
} 


/*  CDS_SETSAMPLELINES -- Set the number of zscale sample lines to use.  */

#ifdef ANSI_FUNC

void 
CDS_SETSAMPLELINES (
    int *nlines				/* no. of sample lines	*/
)
#else

void
CDS_SETSAMPLELINES (nlines)
int	*nlines;			/* no. of sample lines	*/
#endif
{
	CDF_SETSAMPLELINES (nlines);
} 


/*  CDS_SETCONTRAST -- Set the zscale contrast value.  */

#ifdef ANSI_FUNC

void 
CDS_SETCONTRAST (
    float *contrast			/* contrast value	*/
)
#else

void
CDS_SETCONTRAST (contrast)
float	*contrast;			/* contrast value	*/
#endif
{
	CDF_SETCONTRAST (contrast);
} 


/*  CDS_SETNAME -- Set the image name for the WCS string.  */

#ifdef ANSI_FUNC

void 
CDS_SETNAME (
    char *imname			/* image name		*/
)
#else

void
CDS_SETNAME (imname)
char	*imname;			/* image name		*/
#endif
{
	strpak (imname, cstr, SZ_FNAME);
	CDF_SETNAME (imname, SZ_FNAME);
} 


/*  CDS_SETTITLE -- Set the image title for the WCS string.  */

#ifdef ANSI_FUNC

void 
CDS_SETTITLE (
    char *imtitle			/* image title		*/
)
#else

void
CDS_SETTITLE (imtitle)
char	*imtitle;			/* image title		*/
#endif
{
	strpak (imtitle, cstr, SZ_FNAME);
	CDF_SETTITLE (imtitle, SZ_FNAME);
} 


/*  CDS_GETFRAME -- Get the current display frame.  */

#ifdef ANSI_FUNC

void 
CDS_GETFRAME (
    int *frame				/* frame number		*/
)
#else

void
CDS_GETFRAME (frame)
int	*frame;				/* frame number		*/
#endif
{
	CDF_GETFRAME (frame);
} 


/*  CDS_GETZTRANS -- Get the current zscale transform parameters.  */

#ifdef ANSI_FUNC

void 
CDS_GETZTRANS (
    int *ztrans                        	/* z-transform type     */
)
#else

void
CDS_GETZTRANS (ztrans)
int     *ztrans;                        /* z-transform type     */
#endif
{
	CDF_GETZTRANS (ztrans);
} 


/*  CDS_GETZSCALE -- Get the current zscale transform parameters.  */

#ifdef ANSI_FUNC

void 
CDS_GETZSCALE (
    float *z1,
    float *z2                       	/* zscale values        */
)
#else

void
CDS_GETZSCALE (z1, z2)
float   *z1, *z2;                       /* zscale values        */
#endif
{
	CDF_GETZSCALE (z1, z2);
} 


/*  CDS_GETSAMPLE -- Get the number of zscale sample points to use.  */

#ifdef ANSI_FUNC

void 
CDS_GETSAMPLE (
    int *nsample                       	/* no. of sample pts    */
)
#else

void
CDS_GETSAMPLE (nsample)
int     *nsample;                       /* no. of sample pts    */
#endif
{
	CDF_GETSAMPLE (nsample);
} 


/*  CDS_GETSAMPLELINES -- Get the number of zscale sample lines to use.  */

#ifdef ANSI_FUNC

void 
CDS_GETSAMPLELINES (
    int *nlines                        	/* no. of sample lines  */
)
#else

void
CDS_GETSAMPLELINES (nlines)
int     *nlines;                        /* no. of sample lines  */
#endif
{
	CDF_GETSAMPLELINES (nlines);
} 


/*  CDS_GETCONTRAST -- Get the zscale contrast value.  */

#ifdef ANSI_FUNC

void 
CDS_GETCONTRAST (
    float *contrast                     /* contrast value       */
)
#else

void
CDS_GETCONTRAST (contrast)
float   *contrast;                      /* contrast value       */
#endif
{
	CDF_GETCONTRAST (contrast);
} 


/*  CDS_GETNAME -- Get the image name for the WCS string.  */

#ifdef ANSI_FUNC

void 
CDS_GETNAME (
    char *imname                        /* image name           */
)
#else

void
CDS_GETNAME (imname)
char    *imname;                        /* image name           */
#endif
{
	CDF_GETNAME (cstr, SZ_FNAME);
	strupk (cstr, imname, SZ_FNAME);
} 


/*  CDS_GETTITLE -- Get the image title for the WCS string.  */

#ifdef ANSI_FUNC

void 
CDS_GETTITLE (
    char *imtitle                       /* image title          */
)
#else

void
CDS_GETTITLE (imtitle)
char    *imtitle;                       /* image title          */
#endif
{
	CDF_GETTITLE (cstr, SZ_FNAME);
	strupk (cstr, imtitle, SZ_FNAME);
} 


/*  CDS_MAPFRAME -- Map the current frame buffer as an image for overlay.  */

#ifdef ANSI_FUNC

void 
CDS_MAPFRAME (
    int *frame,				/* fb frame to map	*/
    int *ier				/* error code		*/
)
#else

void
CDS_MAPFRAME (frame, ier)
int	*frame;				/* fb frame to map	*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MAPFRAME (frame, ier);
} 

/*  CDF_MARKCOORDSFILE -- Mark a list of coords from a file. */

#ifdef ANSI_FUNC

void
CDS_MARKCOORDSFILE (
    char *fname,                        /* file name            */
    int  *type,                         /* marker type          */
    int  *size,                         /* marker size          */
    int  *color,                        /* marker color         */
    int  *label,                        /* label?               */
    int  *ier                           /* error code           */
)
#else

void
CDS_MARKCOORDSFILE (fname, type, size, color, label, ier)
char    *fname;                         /* file name            */
int     *type;                          /* marker type          */
int     *size;                          /* marker size          */
int     *color;                         /* marker color         */
int     *label;                         /* label?               */
int     *ier;                           /* error code           */
#endif
{
	strpak (fname, cstr, SZ_FNAME);
        CDF_MARKCOORDSFILE (cstr, type, size, color, label, ier, SZ_FNAME);
}


/*  CDS_MARKPOINT --  Draw a mark on the display at the given point. */

#ifdef ANSI_FUNC

void 
CDS_MARKPOINT (
    int *x,
    int *y,				/* marker position	*/
    int *number,			/* if > 0, label value	*/
    int *size,				/* marker size (pixels) */
    int *type,				/* type to draw		*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKPOINT (x, y, number, size, type, color, ier)
int	*x, *y;				/* marker position	*/
int	*number;			/* if > 0, label value	*/
int	*size;				/* marker size (pixels) */
int	*type;				/* type to draw		*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKPOINT (x, y, number, size, type, color, ier);
} 


/*  CDS_MARKPOINTLABEL --  Draw a mark on the display at the given point. */

#ifdef ANSI_FUNC

void 
CDS_MARKPOINTLABEL (
    int *x,
    int *y,				/* marker position	*/
    char *label,			/* point label string	*/
    int *size,				/* marker size (pixels) */
    int *type,				/* type to draw		*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKPOINTLABEL (x, y, label, size, type, color, ier)
int	*x, *y;				/* marker position	*/
char	*label;				/* point label string	*/
int	*size;				/* marker size (pixels) */
int	*type;				/* type to draw		*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	strpak (label, cstr, SZ_FNAME);
	CDF_MARKPOINTLABEL (x, y, cstr, size, type, color, ier, SZ_FNAME);
} 


/*  CDS_MARKLINE --  Draw a line of given color between two points.  */

#ifdef ANSI_FUNC

void 
CDS_MARKLINE (
    int *xs,
    int *ys,				/* line start points	*/
    int *xe,
    int *ye,				/* line end points	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKLINE (xs, ys, xe, ye, color, ier)
int	*xs, *ys;			/* line start points	*/
int	*xe, *ye;			/* line end points	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKLINE (xs, ys, xe, ye, color, ier);
} 


/*  CDS_MARKBOX --  Draw a rectangular box given two corner endpoints.  */

#ifdef ANSI_FUNC

void 
CDS_MARKBOX (
    int *lx,
    int *ly,				/* LL corner points	*/
    int *ux,
    int *uy,				/* UR corner points	*/
    int *fill,				/* fill rectangle?	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKBOX (lx, ly, ux, uy, fill, color, ier)
int	*lx, *ly;			/* LL corner points	*/
int	*ux, *uy;			/* UR corner points	*/
int	*fill;				/* fill rectangle?	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKBOX (lx, ly, ux, uy, fill, color, ier);
} 


/*  CDS_MARKPOLYGON -- Draw a polygon on the display, optionally filling.  */

#ifdef ANSI_FUNC

void 
CDS_MARKPOLYGON (
    int *xarray,
    int *yarray,			/* vertex points	*/
    int *npts,				/* number of corners	*/
    int *fill,				/* fill polygon?	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKPOLYGON (xarray, yarray, npts, fill, color, ier)
int	*xarray, *yarray;		/* vertex points	*/
int	*npts;				/* number of corners	*/
int	*fill;				/* fill polygon?	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKPOLYGON (xarray, yarray, npts, fill, color, ier);
} 


/*  CDS_MARKPOLYLINE -- Draw a polyline on the display, optionally filling.  */

#ifdef ANSI_FUNC

void 
CDS_MARKPOLYLINE (
    int *xarray,
    int *yarray,			/* vertex points	*/
    int *npts,				/* number of points	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKPOLYLINE (xarray, yarray, npts, color, ier)
int	*xarray, *yarray;		/* vertex points	*/
int	*npts;				/* number of points	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKPOLYLINE (xarray, yarray, npts, color, ier);
} 


/*  CDS_MARKCIRCLE -- Draw of circle on the display, optionally filling.  */

#ifdef ANSI_FUNC

void 
CDS_MARKCIRCLE (
    int *x,
    int *y,				/* center position	*/
    int *radius,			/* radius of circle	*/
    int *fill,				/* fill circle?		*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKCIRCLE (x, y, radius, fill, color, ier)
int	*x, *y;				/* center position	*/
int	*radius;			/* radius of circle	*/
int	*fill;				/* fill circle?		*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKCIRCLE (x, y, radius, fill, color, ier);
} 


/*  CDS_MARKCIRCANNULI -- Draw circular annuli on the display.  */

#ifdef ANSI_FUNC

void 
CDS_MARKCIRCANNULI (
    int *x,
    int *y,				/* center position	*/
    int *radius,			/* radius of 1st annulus*/
    int *nannuli,			/* no. of annuli	*/
    int *sep,				/* annuli sep (pixels)	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKCIRCANNULI (x, y, radius, nannuli, sep, color, ier)
int	*x, *y;				/* center position	*/
int	*radius;			/* radius of 1st annulus*/
int	*nannuli;			/* no. of annuli	*/
int	*sep;				/* annuli sep (pixels)	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKCIRCANNULI (x, y, radius, nannuli, sep, color, ier);
} 


/*  CDS_MARKELLIPSE -- Draw an ellipse.  */

#ifdef ANSI_FUNC

void 
CDS_MARKELLIPSE (
    int *x,
    int *y,				/* center position	*/
    int *xrad,
    int *yrad,				/* x and y radii	*/
    float *ang,				/* position angle (deg) */
    int *fill,				/* fill ellipse?	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKELLIPSE (x, y, xrad, yrad, ang, fill, color, ier)
int	*x, *y;				/* center position	*/
int	*xrad, *yrad;			/* x and y radii	*/
float	*ang;				/* position angle (deg) */
int	*fill;				/* fill ellipse?	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKELLIPSE (x, y, xrad, yrad, ang, fill, color, ier);
} 


/*  CDS_MARKELLIPANNULI -- Draw elliptical annuli on the display.  */

#ifdef ANSI_FUNC

void 
CDS_MARKELLIPANNULI (
    int *x,
    int *y,				/* center position	*/
    int *xrad,
    int *yrad,				/* radius of 1st annulus*/
    float *ang,				/* rotation angle	*/
    int *nannuli,			/* no. of annuli	*/
    int *sep,				/* annuli sep (pixels)	*/
    int *color,				/* marker color		*/
    int *ier				/* error code		*/
)
#else

void
CDS_MARKELLIPANNULI (x, y, xrad, yrad, ang, nannuli, sep, color, ier)
int	*x, *y;				/* center position	*/
int	*xrad, *yrad;			/* radius of 1st annulus*/
float	*ang;				/* rotation angle	*/
int	*nannuli;			/* no. of annuli	*/
int	*sep;				/* annuli sep (pixels)	*/
int	*color;				/* marker color		*/
int	*ier;				/* error code		*/
#endif
{
	CDF_MARKELLIPANNULI (x, y, xrad, yrad, ang, nannuli, sep, color, ier);
} 


/*  CDS_MARKTEXT -- Draw a text string on the display at the given location.  */

#ifdef ANSI_FUNC

void 
CDS_MARKTEXT (
    int *x,
    int *y,                         	/* marker position      */
    char *str,                          /* text string          */
    float *size,                        /* size scale factor    */
    float *angle,			/* text rotation angle	*/
    int *color,                         /* marker color         */
    int *ier				/* error code		*/
)
#else

void
CDS_MARKTEXT (x, y, str, size, angle, color, ier)
int     *x, *y;                         /* marker position      */
char    *str;                           /* text string          */
float   *size;                          /* size scale factor    */
float	*angle;				/* text rotation angle	*/
int     *color;                         /* marker color         */
int	*ier;				/* error code		*/
#endif
{
	strpak (str, cstr, SZ_FNAME);
	CDF_MARKTEXT (x, y, cstr, size, angle, color, ier, SZ_FNAME);
} 


/*  CDS_SETFONT -- Set the font to be used. */

#ifdef ANSI_FUNC

void 
CDS_SETFONT (
    int *font				/* font type		*/
)
#else

void
CDS_SETFONT (font)
int	*font;				/* font type		*/
#endif
{
	CDF_SETFONT (font);
} 


/*  CDS_SETLINEWIDTH -- Set the line width to be used. */

#ifdef ANSI_FUNC

void 
CDS_SETLINEWIDTH (
    int *width				/* line width		*/
)
#else

void
CDS_SETLINEWIDTH (width)
int	*width;				/* line width		*/
#endif
{
	CDF_SETLINEWIDTH (width);
} 


/*  CDS_SETLINESTYLE -- Set the line style to be used. */

#ifdef ANSI_FUNC

void
CDS_SETLINESTYLE (
    int *style                          /* line style           */
)
#else

void
CDS_SETLINESTYLE (style)
int     *style;                         /* line style           */
#endif
{
        CDF_SETLINESTYLE (style);
}


/*  CDS_SETTEXTWIDTH -- Set the line width to be used. */

#ifdef ANSI_FUNC

void 
CDS_SETTEXTWIDTH (
    int *width				/* line width		*/
)
#else

void
CDS_SETTEXTWIDTH (width)
int	*width;				/* line width		*/
#endif
{
	CDF_SETTEXTWIDTH (width);
} 


/*  CDS_DELETEMARK -- Delete the overlay mark whose center is closest.  */

#ifdef ANSI_FUNC

void 
CDS_DELETEMARK (
    int *x,
    int *y,				/* marker position	*/
    int *ier				/* error code		*/
)
#else

void
CDS_DELETEMARK (x, y, ier)
int	*x, *y;				/* marker position	*/
int	*ier;				/* error code		*/
#endif
{
	CDF_DELETEMARK (x, y, ier);
} 


/*  CDS_CLEAROVERLAY -- Erase all marks in the current display list.  */

#ifdef ANSI_FUNC

void 
CDS_CLEAROVERLAY (
    int *ier				/* error code		*/
)
#else

void
CDS_CLEAROVERLAY  (ier)
int	*ier;				/* error code		*/
#endif
{
	CDF_CLEAROVERLAY  (ier);
} 
 

/*  CDS_REDRAWOVERLAY -- Redraw all marks in the current display list.  */

#ifdef ANSI_FUNC

void 
CDS_REDRAWOVERLAY (
    int *ier				/* error code		*/
)
#else

void
CDS_REDRAWOVERLAY  (ier)
int	*ier;				/* error code		*/
#endif
{
	CDF_REDRAWOVERLAY  (ier);
} 


/* Debug routine. */
#ifdef ANSI_FUNC

void 
CDS_SETDEBUG (int *state)
#else

void CDS_SETDEBUG (state) int	*state;
#endif
 { cdl_setDebug (*state); }


/* -------------------
 * PRIVATE PROCEDURES
 * -------------------*/


/* STRUPK -- Unpack a C string into an SPP string.
 */

#ifdef ANSI_FUNC

static void 
strupk (
    char *str,                  	/* C string                     */
    char *outstr,              		/* SPP string                   */
    int maxch                  		/* max chars out, incl EOS      */
)
#else

static void
strupk (str, outstr, maxch)
char    *str;                   	/* C string                     */
char   *outstr;                		/* SPP string                   */
int     maxch;                  	/* max chars out, incl EOS      */
#endif
{
        register char   *ip = str;
        register short  *op = (short *)outstr;
        register int      n = maxch-1;

        /* Is is necessary to determine the length of the string in order to
         * be able to unpack the string in place, i.e., from right to left.
         */
        if (maxch)
            if (str != (char *)outstr) {
                n = min (n, strlen(ip));
                op[n] = '\0';

                for (n = n - 1;  n >= 0;  --n)
                    op[n] = ip[n];
            }
}


/* STRPAK -- Pack an SPP string (type XCHAR) into a C string in a user
 * supplied buffer.  Return a pointer to the output buffer.
 */

#ifdef ANSI_FUNC

static void 
strpak (
    char *sppstr,              		/* SPP string                   */
    char *cstr,                 	/* C string                     */
    int maxch                  		/* max chars out, incl EOS      */
)
#else

static void
strpak (sppstr, cstr, maxch)
char    *sppstr;                	/* SPP string                   */
char    *cstr;                  	/* C string                     */
int     maxch;                  	/* max chars out, incl EOS      */
#endif
{
        register short  *ip = (short *)sppstr;
        register char   *op = cstr;
        register int      n = maxch-1;

        if (maxch)
            if ((char *)sppstr != cstr) {
                while (--n >= 0 && (*op++ = *ip++) != '\0')
                    ;
                cstr[maxch-1] = '\0';
            }
}
