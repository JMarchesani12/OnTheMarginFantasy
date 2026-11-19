export type TeamSearchCatalogEntry = {
  teamId: number;
  schoolId: number;
  teamName: string;
  aliases: string[];
};
export type TeamSearchCatalog = { teams: TeamSearchCatalogEntry[] };
