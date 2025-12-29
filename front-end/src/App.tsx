import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./screens/Home/Home";
import CreateLeague from "./screens/CreateLeague/CreateLeague";
import LeagueDetailPage from "./screens/League/LeagueDetailPage";
import LeagueRosterPage from "./screens/League/LeagueRosterPage";
import LeagueDraftPage from "./screens/League/LeagueDraftPage";
import SignIn from "./screens/Auth/SignIn";
import ConferenceSchedulePage from "./screens/League/ConferenceSchedulePage";
import TeamSchedulePage from "./screens/League/TeamSchedulePage";
import ManageLeaguePage from "./screens/League/ManageLeaguePage";
import DiscoverLeaguePage from "./screens/League/DiscoverLeaguePage";
import SettingsPage from "./screens/Settings/SettingsPage";

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SignIn />} />
        <Route path="/leagues" element={<Home />} />
        <Route path="/leagues/new" element={<CreateLeague />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/leagues/:league_id" element={<LeagueDetailPage />} />
        <Route
          path="/leagues/discover/:league_id"
          element={<DiscoverLeaguePage />}
        />
        <Route path="/leagues/:league_id/roster" element={<LeagueRosterPage />} />
        <Route path="/leagues/:league_id/draft" element={<LeagueDraftPage />} />
        <Route path="/leagues/:league_id/manage" element={<ManageLeaguePage />} />
        <Route path="/leagues/:league_id/conference" element={<ConferenceSchedulePage />} />
        <Route path="/leagues/:league_id/teams/:team_id" element={<TeamSchedulePage />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
