import React, { Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";

const Home = React.lazy(() => import("./screens/Home/Home"));
const CreateLeague = React.lazy(() => import("./screens/CreateLeague/CreateLeague"));
const LeagueDetailPage = React.lazy(() => import("./screens/League/LeagueDetailPage"));
const LeagueRosterPage = React.lazy(() => import("./screens/League/LeagueRosterPage"));
const LeagueDraftPage = React.lazy(() => import("./screens/League/LeagueDraftPage"));
const SignIn = React.lazy(() => import("./screens/Auth/SignIn"));
const LandingPage = React.lazy(() => import("./screens/Landing/LandingPage"));
const ConferenceSchedulePage = React.lazy(
  () => import("./screens/League/ConferenceSchedulePage")
);
const TeamSchedulePage = React.lazy(
  () => import("./screens/League/TeamSchedulePage")
);
const ManageLeaguePage = React.lazy(
  () => import("./screens/League/ManageLeaguePage")
);
const DiscoverLeaguePage = React.lazy(
  () => import("./screens/League/DiscoverLeaguePage")
);
const SettingsPage = React.lazy(() => import("./screens/Settings/SettingsPage"));

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="app-loading">Loading…</div>}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/leagues" element={<Home />} />
          <Route path="/leagues/new" element={<CreateLeague />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/leagues/:league_id" element={<LeagueDetailPage />} />
          <Route
            path="/leagues/discover/:league_id"
            element={<DiscoverLeaguePage />}
          />
          <Route
            path="/leagues/:league_id/roster"
            element={<LeagueRosterPage />}
          />
          <Route path="/leagues/:league_id/draft" element={<LeagueDraftPage />} />
          <Route
            path="/leagues/:league_id/manage"
            element={<ManageLeaguePage />}
          />
          <Route
            path="/leagues/:league_id/conference"
            element={<ConferenceSchedulePage />}
          />
          <Route
            path="/leagues/:league_id/teams/:team_id"
            element={<TeamSchedulePage />}
          />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

export default App;
