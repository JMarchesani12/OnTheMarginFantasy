import { Link } from "react-router-dom";
import { siteInfo } from "../../lib/siteInfo";
import "./LegalPage.css";

type Props = { policy: "privacy" | "terms" };

export default function LegalPage({ policy }: Props) {
  const privacy = policy === "privacy";
  return (
    <main className="legal-page">
      <Link to="/">← On The Margin Fantasy</Link>
      <h1>{privacy ? "Privacy Policy" : "Terms of Service"}</h1>
      <p className="legal-page__notice">Draft for review — these policies are being finalized. Last updated November 23, 2026.</p>
      {privacy ? <>
        <section><h2>Information used by the service</h2>
          <p>On The Margin Fantasy uses account information, including your email address, username, and authentication information, to provide access to fantasy leagues. League activity includes memberships, team names, drafts, rosters, transactions, settings, and scores.</p>
        </section>
        <section><h2>How information is used and displayed</h2>
          <p>Information supports sign-in, league administration, gameplay, scoring, and account support. Usernames, fantasy team names, rosters, and scores may appear to other users through league features. Public league discovery can display league details and commissioner display names.</p>
        </section>
        <section><h2>Authentication and browser storage</h2>
          <p>Supabase provides account authentication. The app stores authentication sessions in your browser to keep you signed in, and uses browser storage for preferences and cached app information. Signing out ends your app session.</p>
        </section>
        <section><h2>Service providers and feedback</h2>
          <p>Account and application information is processed through the services used to authenticate users, host the app, and store league information. When you use the feedback form, the app prepares an email; the message is sent through your email provider only when you send it. Include only information needed to explain your request.</p>
        </section>
        <section><h2>Access, corrections, and deletion requests</h2>
          <p>You can update your display name in Settings. Contact us to request access, corrections, or deletion of account information. We may need to verify account ownership. Some league records may need to be retained to preserve shared league history or meet applicable obligations.</p>
        </section>
        <section><h2>Policy updates</h2><p>Changes will be posted on this page with an updated date. The final policy will describe the service’s confirmed provider, retention, and privacy practices.</p></section>
      </> : <>
        <section><h2>Using On The Margin Fantasy</h2><p>The service provides tools to create and participate in fantasy sports leagues. Keep your account credentials secure and provide accurate account information. You are responsible for activity through your account.</p></section>
        <section><h2>League rules and commissioner decisions</h2><p>Review your league’s rules before joining or drafting. League settings, deadlines, roster limits, and scoring rules determine gameplay. Commissioners manage their leagues through the available tools. Report errors or disputes with enough detail for review.</p></section>
        <section><h2>Acceptable use</h2><p>Do not harass other users, impersonate others, attempt unauthorized access, disrupt the service, or misuse league and account tools. Access may be restricted to address abuse or security concerns.</p></section>
        <section><h2>Scores, schedules, and availability</h2><p>Schedules and scores depend on external sports data and may be delayed, incomplete, or corrected. Corrections can affect league results. Uninterrupted service and error-free data are not guaranteed.</p></section>
        <section><h2>Payments and prizes</h2><p>Do not assume that the app collects entry fees, holds funds, guarantees prizes, or administers arrangements made between league members. Any future platform payment or prize features need their own published terms.</p></section>
        <section><h2>Content and ownership</h2><p>The app’s original software, design, and written content belong to their respective owners. Third-party names, logos, and content remain the property of their owners. Use of a school, team, or conference name does not imply endorsement or affiliation.</p></section>
        <section><h2>Changes and account issues</h2><p>Features and these terms may change. Updated terms will be posted here. Contact us with account or service questions.</p></section>
      </>}
      <section><h2>Contact</h2>
        {siteInfo.supportEmail ? <p>Email <a href={`mailto:${siteInfo.supportEmail}`}>{siteInfo.supportEmail}</a>.</p>
          : <p>Public contact details are being confirmed.</p>}
        {siteInfo.copyrightOwner && <p>Service operator: {siteInfo.copyrightOwner}.</p>}
      </section>
      <p><Link to={privacy ? "/terms" : "/privacy"}>{privacy ? "Terms of Service" : "Privacy Policy"}</Link> · <Link to="/feedback">Help & feedback</Link></p>
    </main>
  );
}
