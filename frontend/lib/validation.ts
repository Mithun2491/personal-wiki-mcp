import { z } from "zod";

export const wikiNameSchema = z.union([
  z.literal(""),
  z
    .string()
    .trim()
    .max(64, "Wiki name is too long")
    .regex(
      /^[A-Za-z0-9][A-Za-z0-9._-]*$/,
      "Wiki name may only contain letters, numbers, dots, dashes, and underscores",
    ),
]);

export const searchQuerySchema = z
  .string()
  .trim()
  .min(1, "Search query cannot be empty")
  .max(200, "Search query is too long");

export const maxResultsSchema = z.coerce
  .number()
  .int()
  .min(1, "maxResults must be at least 1")
  .max(50, "maxResults must be at most 50")
  .default(20);

export const articlePathSchema = z
  .string()
  .trim()
  .max(512, "Article path is too long")
  .refine((v) => v.length > 0, { message: "Article path is required" })
  .refine((v) => !v.includes("\0"), { message: "Invalid article path" })
  .refine((v) => !v.includes("\\"), { message: "Invalid article path" })
  .refine((v) => !v.includes(":"), { message: "Invalid article path" })
  .refine((v) => !v.startsWith("/"), { message: "Article path must be relative" })
  .refine(
    (v) =>
      !v.split("/").some((seg) => seg === "" || seg === "." || seg === ".."),
    { message: "Invalid article path" },
  )
  .refine((v) => /\.md$/i.test(v), {
    message: "Only Markdown files can be read",
  });

const wikiEntrySchema = z.object({
  name: z.string(),
  path: z.string().nullish(),
  description: z.string().nullish(),
  status: z.string(),
  is_hub: z.boolean(),
});

export const wikiListSchema = z.object({
  default: z.string().nullish(),
  count: z.number(),
  truncated: z.boolean(),
  wikis: z.array(wikiEntrySchema),
});

const searchMatchSchema = z.object({
  path: z.string(),
  line: z.number(),
  snippet: z.string(),
});

export const searchResultSchema = z.object({
  query: z.string(),
  wiki: z.string(),
  files_scanned: z.number(),
  match_count: z.number(),
  max_results: z.number(),
  truncated: z.boolean(),
  matches: z.array(searchMatchSchema),
});
