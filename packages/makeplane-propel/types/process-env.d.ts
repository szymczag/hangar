// The recovered source reads `process.env.NODE_ENV` for development-only
// warnings, which consuming bundlers replace at build time. Declared here so
// the type check does not need @types/node.
declare const process: { env: { NODE_ENV?: string } };
