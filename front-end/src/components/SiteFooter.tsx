import { Link, useLocation } from "react-router-dom";
import { siteInfo } from "../lib/siteInfo";
import "./SiteFooter.css";

export default function SiteFooter() {
  const location = useLocation();
  const feedbackLink = (category: "bug" | "feature") => `/feedback?${new URLSearchParams({ category, from: location.pathname })}`;
  return <footer className="site-footer">
    <nav aria-label="Legal and support">
      <Link to="/privacy">Privacy</Link>
      <Link to="/terms">Terms</Link>
      <details key={location.pathname + location.search} className="site-footer__help">
        <summary>Help & feedback</summary>
        <div className="site-footer__menu">
          <Link to={feedbackLink("bug")}>Report a bug</Link>
          <Link to={feedbackLink("feature")}>Suggest a feature</Link>
          <a href={`mailto:${siteInfo.supportEmail}`}>Contact us</a>
        </div>
      </details>
    </nav>
    <small>© {new Date().getFullYear()} {siteInfo.copyrightOwner}</small>
  </footer>;
}
