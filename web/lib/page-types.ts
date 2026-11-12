export type SearchParams = Record<string, string | string[] | undefined>;
export type PageProps = { searchParams: Promise<SearchParams> };
