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

  static computeHash(input: string): string {
    const hash = crypto.pbkdf2Sync(input, this.salt, this.iter, 64, this.hashAlgorithm).toString("hex");

    return hash;
  }
}
