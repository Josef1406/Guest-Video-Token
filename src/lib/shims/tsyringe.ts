// tsyringe checks for the Reflect polyfill when it loads; importing it here guarantees the order in every bundle.
import "reflect-metadata";
// @ts-expect-error resolved to the real package file by the vite alias
export * from "tsyringe-original";
