import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../../lib/supabaseClient";
import "./SignIn.css";

const ResetPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        email.trim(),
        {
          redirectTo: `${window.location.origin}/update-password`,
        }
      );

      if (resetError) {
        throw resetError;
      }

      setMessage("If an account exists for that email, a reset link is on the way.");
    } catch (resetErr: any) {
      setError(resetErr?.message ?? "Failed to send reset email. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="sign-in">
      <section className="sign-in__card">
        <h1>Reset Password</h1>
        <p>Enter your email and we will send you a password reset link.</p>
        <form className="sign-in__form" onSubmit={handleSubmit}>
          <label className="sign-in__label" htmlFor="reset-password-email">
            Email
            <input
              id="reset-password-email"
              type="email"
              className="sign-in__input"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          {error && <p className="sign-in__error">{error}</p>}
          {message && <p className="sign-in__message">{message}</p>}
          <button type="submit" className="sign-in__button" disabled={loading}>
            {loading ? "Sending..." : "Send Reset Link"}
          </button>
        </form>
        <p className="sign-in__switch">
          <Link to="/signin">Back to sign in</Link>
        </p>
      </section>
    </main>
  );
};

export default ResetPassword;
