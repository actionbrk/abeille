import crypto from "crypto";
import logger from "../logger";

export class HashHelper {
  static hashAlgorithm: string = "sha512";
  static iter = 100000;
  static salt = "bee-default-salt";

  static initialize() {
    const overrideHash = process.env.HASHNAME;
    if (overrideHash && overrideHash !== this.hashAlgorithm) {
      logger.info(`Hash algorithm overridden to ${overrideHash}`);
      this.hashAlgorithm = overrideHash;
    }

    const overrideIter = process.env.ITER;
    if (overrideIter && overrideIter !== this.iter.toString()) {
      logger.info(`Hash iterations overridden to ${overrideIter}`);
      this.iter = parseInt(overrideIter);
    }

    const overrideSalt = process.env.SALT;
    if (overrideSalt && overrideSalt !== this.salt) {
      logger.info(`Hash salt overridden to ${overrideSalt}`);
      this.salt = overrideSalt;
    }

    logger.info(`Hash algorithm: ${this.hashAlgorithm}`);
    logger.info(`Hash iterations: ${this.iter}`);
    logger.info(`Hash salt: ${this.salt}`);
  }

  // This cache consumes nearly 350 bytes per entry
  // and is used to store the hash of the discord users id
  // It's ok to use a cache of 1000 entries
  private static cache = new Map<string, string>();

  static computeHash(input: string): string {
    if (this.cache.has(input)) {
      return this.cache.get(input)!;
    }

    const hash = crypto.pbkdf2Sync(input, this.salt, this.iter, 64, this.hashAlgorithm).toString("hex");
    this.cache.set(input, hash);

    return hash;
  }
}
