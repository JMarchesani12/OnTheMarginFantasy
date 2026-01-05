import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import "./SignIn.css";

const PENDING_USER_CREATE_KEY = "otm:pending-user-create";

const SignIn = () => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signIn" | "signUp">("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [username, setUsername] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const isSignUp = mode === "signUp";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      if (isSignUp) {
        if (!username.trim()) {
          throw new Error("Username is required to create an account.");
        }
        if (password !== confirmPassword) {
          throw new Error("Passwords do not match.");
        }

        const { error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: { username: username.trim() },
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });

        if (signUpError) {
          throw signUpError;
        }

        localStorage.setItem(
          PENDING_USER_CREATE_KEY,
          JSON.stringify({ email, displayName: username.trim() })
        );

        setMessage("Check your email to confirm your account, then sign in.");
        setMode("signIn");
        setPassword("");
        setConfirmPassword("");
        setShowPassword(false);
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (signInError) {
          throw signInError;
        }

        navigate("/leagues", { replace: true });
      }
    } catch (authError: any) {
      setError(authError?.message ?? "Authentication failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!email.trim()) {
      setError("Enter your email to resend the verification.");
      return;
    }

    setError(null);
    setMessage(null);
    setResending(true);

    try {
      const { error: resendError } = await supabase.auth.resend({
        type: "signup",
        email: email.trim(),
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });

      if (resendError) {
        throw resendError;
      }

      setMessage("Verification email sent. Check your inbox.");
    } catch (resendErr: any) {
      setError(resendErr?.message ?? "Failed to resend verification email.");
    } finally {
      setResending(false);
    }
  };

  // const handleGoogleSignIn = async () => {
  //   setError(null);
  //   setMessage(null);

  //   try {
  //     const { error: oauthError } = await supabase.auth.signInWithOAuth({
  //       provider: "google",
  //       options: {
  //         redirectTo: `${window.location.origin}/leagues`,
  //       },
  //     });

  //     if (oauthError) {
  //       throw oauthError;
  //     }
  //   } catch (oauthErr: any) {
  //     setError(oauthErr?.message ?? "Google sign-in failed. Try again.");
  //   }
  // };

  return (
    <main className="sign-in">
      <section className="sign-in__card">
        <h1>On the Margin Fantasy</h1>
        <p>{isSignUp ? "Create an account to start managing leagues." : "Sign in to manage your leagues and rosters."}</p>
        <form className="sign-in__form" onSubmit={handleSubmit}>
          {isSignUp && (
            <label className="sign-in__label" htmlFor="sign-in-username">
              Username
              <input
                id="sign-in-username"
                type="text"
                className="sign-in__input"
                placeholder="SickoFan12"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
          )}
          <label className="sign-in__label" htmlFor="sign-in-email">
            Email
            <input
              id="sign-in-email"
              type="email"
              className="sign-in__input"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="sign-in__label" htmlFor="sign-in-password">
            Password
            <div className="sign-in__password-field">
              <input
                id="sign-in-password"
                type={showPassword ? "text" : "password"}
                className="sign-in__input"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                type="button"
                className="sign-in__toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          {isSignUp && (
            <label className="sign-in__label" htmlFor="sign-in-confirm-password">
              Confirm Password
              <div className="sign-in__password-field">
                <input
                  id="sign-in-confirm-password"
                  type={showPassword ? "text" : "password"}
                  className="sign-in__input"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                />
                <button
                  type="button"
                  className="sign-in__toggle"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </label>
          )}
          {error && <p className="sign-in__error">{error}</p>}
          {message && <p className="sign-in__message">{message}</p>}
          <button type="submit" className="sign-in__button" disabled={loading}>
            {loading ? "Please wait…" : isSignUp ? "Create Account" : "Sign In"}
          </button>
          {!isSignUp && (
            <button
              type="button"
              className="sign-in__button sign-in__button--ghost"
              onClick={handleResendVerification}
              disabled={resending}
            >
              {resending ? "Sending…" : "Resend verification email"}
            </button>
          )}
        </form>
        <p className="sign-in__switch">
          <br/>
          {isSignUp ? "Already have an account?" : "Need an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(isSignUp ? "signIn" : "signUp");
              setError(null);
              setMessage(null);
              setConfirmPassword("");
              setShowPassword(false);
            }}
          >
            {isSignUp ? "Sign in" : "Sign up"}
          </button>
        </p>
        {/* <div className="sign-in__divider">
          <span />
          <p>OR</p>
          <span />
        </div>
        <button
          type="button"
          className="sign-in__google"
          onClick={handleGoogleSignIn}
          disabled={loading}
        >
          Continue with Google
        </button> */}
      </section>
    </main>
  );
};

export default SignIn;
