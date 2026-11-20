// Image imports are left external by the build and resolved by the consuming
// bundler, which yields either a URL string or an object with `src`.
declare module "*.gif" {
  const src: string | { src: string };
  export default src;
}

declare module "*.png" {
  const src: string | { src: string };
  export default src;
}
