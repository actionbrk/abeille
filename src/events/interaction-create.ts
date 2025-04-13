import { Events, MessageFlags, type Interaction, type InteractionReplyOptions } from "discord.js";
import type { BeeEvent } from "../models/events";
import logger from "../logger";

const InteractionCreateEvent: BeeEvent<Events.InteractionCreate> = {
  name: Events.InteractionCreate,
  once: false,
  async execute(interaction: Interaction) {
    if (!interaction.isChatInputCommand()) return;

    performance.mark("interactionCreateStart");

    const command = interaction.client.commands?.get(interaction.commandName);

    if (!command) {
      logger.error("Command %s not found.", interaction.commandName);
      await interaction.reply({
        content: "This command is not implemented yet.",
        flags: [MessageFlags.Ephemeral],
      });
      return;
    }

    try {
      await command.execute(interaction);
    } catch (error) {
      logger.error(error);

      const message: InteractionReplyOptions = {
        content: "There was an error while executing this command!",
        flags: MessageFlags.Ephemeral,
      };

      if (interaction.replied || interaction.deferred) {
        await interaction.followUp(message);
      } else {
        await interaction.reply(message);
      }
    }

    performance.mark("interactionCreateEnd");
    performance.measure("interactionCreate", "interactionCreateStart", "interactionCreateEnd");
    logger.info(
      "Handling interaction %s in %i ms",
      interaction.commandName,
      performance.getEntriesByName("interactionCreate")[0]?.duration ?? 0
    );
    performance.clearMarks();
    performance.clearMeasures();
    performance.clearResourceTimings();
  },
};

export default InteractionCreateEvent;
