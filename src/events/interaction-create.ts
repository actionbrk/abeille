import { Events, MessageFlags, type Interaction } from "discord.js";
import type { BeeEvent } from "../models/events";
import logger from "../logger";

const interactionCreate: BeeEvent = {
  name: Events.InteractionCreate,
  async execute(interaction: Interaction) {
    if (!interaction.isChatInputCommand()) return;

    const command = interaction.client.commands?.get(interaction.commandName);

    if (!command) {
      logger.error("No command matching %s was found.", interaction.commandName);
      return;
    }

    try {
      await command.execute(interaction);
    } catch (error) {
      logger.error(error);
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp({
          content: "There was an error while executing this command!",
          flags: MessageFlags.Ephemeral,
        });
      } else {
        await interaction.reply({
          content: "There was an error while executing this command!",
          flags: MessageFlags.Ephemeral,
        });
      }
    }
  },
};

export default interactionCreate;
