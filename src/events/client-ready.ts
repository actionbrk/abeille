import { Events, type Client } from "discord.js";
import logger from "../logger";
import type { BeeEvent } from "../models/events";

const ClientReadyEvent: BeeEvent = {
  name: Events.ClientReady,
  once: true,
  async execute(client: Client) {
    logger.info("Logged in as %s", client.user?.tag);
  },
};

export default ClientReadyEvent;
