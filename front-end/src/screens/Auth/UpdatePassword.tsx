import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import { useAuth } from "../../context/AuthContext";
import "./SignIn.css";

const UpdatePassword = () => {
  const navigate = useNavigate();
  const { session, loading: authLoading } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const redirectError = params.get("error_description") ?? params.get("error");

    if (redirectError) {
      setError(redirectError.replace(/\+/g, " "));
      window.history.replaceState(null, "", window.location.pathname);
      return;
    }

  }, []);

  useEffect(() => {
    if (session && window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [session]);

  useEffect(() => {
    if (!authLoading && !session) {
      setError("Open the password reset link from your email to choose a new password.");
    }
  }, [authLoading, session]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password,
      });

      if (updateError) {
        throw updateError;
      }

      setMessage("Password updated. Redirecting you to sign in...");
      setPassword("");
      setConfirmPassword("");
      setTimeout(() => {
        void supabase.auth.signOut();
        navigate("/signin", { replace: true });
      }, 1000);
    } catch (updateErr: any) {
      setError(updateErr?.message ?? "Failed to update password. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const disabled = loading || authLoading || !session;

  return (
    <main className="sign-in">
      <section className="sign-in__card">
        <h1>Choose New Password</h1>
        <p>Create a new password for your account.</p>
        <form className="sign-in__form" onSubmit={handleSubmit}>
          <label className="sign-in__label" htmlFor="update-password">
            New Password
            <div className="sign-in__password-field">
              <input
                id="update-password"
                type={showPassword ? "text" : "password"}
                className="sign-in__input"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={6}
                disabled={disabled}
              />
              <button
                type="button"
                className="sign-in__toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                disabled={authLoading || !session}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          <label className="sign-in__label" htmlFor="update-confirm-password">
            Confirm Password
            <div className="sign-in__password-field">
              <input
                id="update-confirm-password"
                type={showPassword ? "text" : "password"}
                className="sign-in__input"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
                minLength={6}
                disabled={disabled}
              />
              <button
                type="button"
                className="sign-in__toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                disabled={authLoading || !session}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>
          {error && <p className="sign-in__error">{error}</p>}
          {message && <p className="sign-in__message">{message}</p>}
          <button type="submit" className="sign-in__button" disabled={disabled}>
            {loading ? "Updating..." : "Update Password"}
          </button>
        </form>
        <p className="sign-in__switch">
          <Link to="/signin">Back to sign in</Link>
        </p>
      </section>
    </main>
  );
};

export default UpdatePassword;
