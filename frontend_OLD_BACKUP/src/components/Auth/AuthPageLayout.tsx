import { AuthShell, type AuthShellProps } from "./AuthShell";

export type AuthPageLayoutProps = AuthShellProps;

/** Stable import path for sign-in / sign-up pages — renders `AuthShell`. */
export function AuthPageLayout(props: AuthPageLayoutProps) {
  return <AuthShell {...props} />;
}
