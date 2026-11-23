import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { siteInfo } from "../../lib/siteInfo";
import { feedbackMailto, formatFeedback, type FeedbackCategory } from "../../utils/feedback";
import "../Legal/LegalPage.css";
import "./FeedbackPage.css";

export default function FeedbackPage() {
  const [params, setParams] = useSearchParams();
  const category: FeedbackCategory = params.get("category") === "feature" ? "feature" : "bug";
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [expected, setExpected] = useState("");
  const [includePage, setIncludePage] = useState(false);
  const [status, setStatus] = useState("");
  const [showCopy, setShowCopy] = useState(false);
  const source = params.get("from") ?? "";
  const page = source.startsWith("/") && !source.startsWith("//") ? source.split(/[?#]/)[0] : "";
  const message = formatFeedback(category, title, details, expected, includePage ? page : "");
  const copyText = `To: ${siteInfo.supportEmail}\nSubject: ${message.subject}\n\n${message.body}`;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    window.location.href = feedbackMailto(siteInfo.supportEmail, message.subject, message.body);
    setStatus("Email draft requested. Send it from your email app to submit your feedback. If nothing opened, use Copy message or email us directly.");
  };

  return <main className="feedback-page">
    <Link to="/">← On The Margin Fantasy</Link>
    <h1>Help & feedback</h1>
    <p>Found a problem or have an idea? Tell us about it.</p>
    <form onSubmit={submit}>
      <label>Feedback type<select value={category} onChange={event => {
        const next = new URLSearchParams(params);
        next.set("category", event.target.value);
        setParams(next, { replace: true });
        setStatus("");
      }}><option value="bug">Report a bug</option><option value="feature">Suggest a feature</option></select></label>
      <label>Summary<input value={title} onChange={event => setTitle(event.target.value)} maxLength={120} required pattern=".*\S.*" /></label>
      <label>{category === "bug" ? "What happened? How can we reproduce it?" : "What would you like to do, and how would it help?"}
        <textarea value={details} onChange={event => setDetails(event.target.value)} maxLength={3000} rows={6} required />
      </label>
      {category === "bug" && <label>What did you expect to happen? (optional)
        <textarea value={expected} onChange={event => setExpected(event.target.value)} maxLength={1000} rows={3} />
      </label>}
      {page && <label className="feedback-page__checkbox"><input type="checkbox" checked={includePage} onChange={event => setIncludePage(event.target.checked)} />Include page address: {page}</label>}
      <p className="feedback-page__hint">Don’t include passwords, payment details, or other sensitive information. This form opens an email draft; it does not send automatically.</p>
      <div className="feedback-page__actions">
        <button type="submit" disabled={!title.trim() || !details.trim()}>Open email draft</button>
        <button type="button" onClick={async () => {
          try { await navigator.clipboard.writeText(copyText); setStatus("Message copied. Paste it into an email and send it to us."); }
          catch { setShowCopy(true); setStatus("Copy the message below into your email app."); }
        }}>Copy message</button>
      </div>
      {status && <p role="status">{status}</p>}
      {showCopy && <label>Message to copy<textarea readOnly value={copyText} rows={10} onFocus={event => event.target.select()} /></label>}
    </form>
    <p>You can also email <a href={`mailto:${siteInfo.supportEmail}`}>{siteInfo.supportEmail}</a>. You can attach screenshots in your email app.</p>
    <p><Link to="/privacy">Privacy Policy</Link></p>
  </main>;
}
