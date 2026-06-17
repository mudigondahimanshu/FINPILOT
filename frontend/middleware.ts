import { NextResponse, type NextRequest } from "next/server";

// Gate protected routes by the *presence* of the refresh cookie. The cookie is
// httpOnly so JS can't read it, but middleware (server-side) can — enough to
// redirect anonymous users to /login. Real authorization still happens on the
// API via the bearer token; this is purely a navigation guard.
const PROTECTED = ["/dashboard"];
const AUTH_PAGES = ["/login", "/register"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has("refresh_token");

  if (PROTECTED.some((p) => pathname.startsWith(p)) && !hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  if (AUTH_PAGES.includes(pathname) && hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login", "/register"],
};
