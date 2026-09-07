/**
 * The names the two processes use to talk about exporting.
 *
 * Their own file because both ends need them and neither end may import the
 * other: the preload script runs in a sandbox with no filesystem, so pulling
 * these out of the main process module would drag `node:fs` in with them and
 * fail at load. A file with no imports can be shared safely — including for
 * the one type that crosses the boundary, which lives here rather than beside
 * the code that builds it so that importing it can never reach the filesystem
 * either, erased type import or not.
 */

/** A folder the person chose, and what an export there would destroy. */
export type ChosenDirectory = { path: string; existingPdfs: number };

export const CHOOSE_DIRECTORY_CHANNEL = "resume-export:choose-directory";
export const CLEAR_CHANNEL = "resume-export:clear";
export const WRITE_CHANNEL = "resume-export:write";
