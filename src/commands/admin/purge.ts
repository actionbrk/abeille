import { InteractionContextType, PermissionFlagsBits, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import {
  cleanOldChannels,
  initializeMessageDays,
  optimizeDatabase,
  purgeDeletedMessages,
} from "../../database/bee-database";
import logger from "../../logger";

const translations = LocaleHelper.getCommandTranslations("purge");

const PurgeCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("purge")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Clean deleted messages from the database.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const guild = interaction.guild!;

    let deletedCount = 0;
    let checkedCount = 0;
    const deletedIds: string[] = [];

    // Get all text channels
    const textChannels = guild.channels.cache.filter((channel) => channel.viewable);

    const progressMessage = await interaction.editReply({
      content: translations.responses?.scanning?.[interaction.locale] ?? "Scanning channels for deleted messages...",
    });

    // Check each channel
    for (const [, channel] of textChannels) {
      try {
        if (!channel.isTextBased()) continue;

        const messages = await channel.messages.fetch({ limit: 100 });
        checkedCount += messages.size;

        // Any message not found in Discord but in our database should be deleted
        const messageIds = messages.map((m) => m.id);
        const missingIds = messageIds.filter((id) => !messages.has(id.toString()));
        deletedIds.push(...missingIds);

        if (missingIds.length > 0) {
          deletedCount += missingIds.length;
          await progressMessage.edit({
            content: (
              translations.responses?.progress?.[interaction.locale] ??
              "Found {deleted} deleted messages in {checked} checked messages..."
            )
              .replace("{deleted}", deletedCount.toString())
              .replace("{checked}", checkedCount.toString()),
          });
        }
      } catch (error) {
        logger.warn("Error checking channel %s: %o", channel.id, error);
      }
    }

    const channelsIds = textChannels.map((channel) => channel.id);
    logger.info("Checked %d channels in guild %s", channelsIds.length, guildId);

    cleanOldChannels(guildId, channelsIds);
    logger.info("Cleaned old channels in guild %s", guildId);

    initializeMessageDays(guildId);
    await optimizeDatabase(guildId);

    if (deletedIds.length > 0) {
      // Delete messages in batches
      const batchSize = 1000;
      for (let i = 0; i < deletedIds.length; i += batchSize) {
        const batch = deletedIds.slice(i, i + batchSize);
        const purgedCount = purgeDeletedMessages(guildId, batch);
        logger.info("Purged %d messages from batch in guild %s", purgedCount, guildId);
      }

      await progressMessage.edit({
        content: (
          translations.responses?.success?.[interaction.locale] ??
          "Successfully removed {count} deleted messages from the database."
        ).replace("{count}", deletedCount.toString()),
      });
    } else {
      await progressMessage.edit({
        content:
          translations.responses?.noDeleted?.[interaction.locale] ?? "No deleted messages found in the database.",
      });
    }
  },
};

export default PurgeCommand;
