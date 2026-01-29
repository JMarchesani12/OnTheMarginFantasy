export type DraftPickResponse = {
    createdAt: Date;
    id: number;
    leagueId: number;
    leagueTeamSlotId: number;
    memberId: number;
    overallPickNumber: number;
    pickInRound: number;
    roundNumber: number;
    sportTeamId: number;
    draftComplete: boolean;
    nextMemberId?: number;
    nextOverallPickNumber?: number;
}

export type FreeAgencyResponse = {
    added: number | null;
    dropped: number | null;
    leagueId: number;
    memberId: number;
    memberRosterTeamIds: number[];
    transactionId: number;
    type: string;
    weekId: number;
    weekNumber: number;
}

export type TradeResponseAction = "ACCEPT" | "REJECT"

export type TradeResponse = {
    transactionId: number;
    status: string;
}

type Team = {
    displayName: string;
    id: number
}

export type TradeStatus = {
    createdAt: Date;
    fromTeams: Team[];
    toTeams: Team[];
    leagueId: number;
    status: string;
    memberFromTeamName: string;
    memberFromDisplayName: string;
    memberToTeamName: string;
    memberToDisplayName: string;
    memberFromId: number;
    memberToId: number;
    memberHasVetoed: boolean;
    transactionId: number;
    type: string;
    weekId: number;
    weekNumber: number;
}

type MyTrades = {
    incoming: TradeStatus[];
    outgoing: TradeStatus[];
}

export type OpenTradesResponse = {
    memberId: number;
    mine: MyTrades;
    others: TradeStatus[];
}

export type VetoResponse = {
    memberVetoed: boolean;
    requiredVetoCount: number;
    status: string;
    transactionId: number;
    vetoCount: number;
}

export type PendingTransaction = {
    id: number;
    leagueId: number;
    weekId: number | null;
    weekNumber: number | null;
    type: string;
    status: string;
    memberFromId: number | null;
    memberToId: number | null;
    fromTeamIds?: number[] | null;
    toTeamIds?: number[] | null;
    fromTeams?: Team[] | null;
    toTeams?: Team[] | null;
    memberFromDisplayName?: string | null;
    memberToDisplayName?: string | null;
    createdAt: string;
};

export type PendingTransactionsResponse = PendingTransaction[];
