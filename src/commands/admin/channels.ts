import { EmbedBuilder, InteractionContextType, PermissionFlagsBits, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getChannelStats } from "../../database/bee-database";

const translations = LocaleHelper.getCommandTranslations("channels");

const ChannelsCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("channels")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("List all tracked channels and their message counts.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const guild = interaction.guild!;

    const channelStats = getChannelStats(guildId);
    const textChannels = guild.channels.cache.filter((channel) => channel.viewable);

    const embed = new EmbedBuilder()
      .setTitle(translations.responses?.title?.[interaction.locale] ?? "Channel Statistics")
      .setColor(0xffff00);

    // Group channels by category
    const categorizedChannels = new Map<string | null, { name: string; count: number }[]>();

    textChannels.forEach((channel) => {
      if (!channel.isTextBased()) {
        return;
      }

      const categoryName = channel.parent?.name ?? null;
      const stats = channelStats.get(channel.id);

      if (!categorizedChannels.has(categoryName)) {
        categorizedChannels.set(categoryName, []);
      }

      categorizedChannels.get(categoryName)!.push({
        name: channel.name,
        count: stats?.count ?? 0,
      });
    });

    // Sort categories and channels by name
    const sortedCategories = Array.from(categorizedChannels.entries()).sort(([a], [b]) => {
      if (a === null) return 1;
      if (b === null) return -1;
      return a.localeCompare(b);
    });

    // Create fields for each category
    for (const [category, channels] of sortedCategories) {
      const sortedChannels = channels.sort((a, b) => b.count - a.count);
      const fieldContent = sortedChannels.map((ch) => `#${ch.name}: ${ch.count.toLocaleString()} messages`).join("\n");

      if (fieldContent.length > 0) {
        embed.addFields({
          name: category ?? "No Category",
          value: fieldContent,
        });
      }
    }

    // Add total statistics
    const totalMessages = Array.from(channelStats.values()).reduce((sum, stats) => sum + stats.count, 0);
    const trackedChannels = channelStats.size;

    embed.setFooter({
      text: (translations.responses?.footer?.[interaction.locale] ?? "Total: {total} messages in {channels} channels")
        .replace("{total}", totalMessages.toLocaleString())
        .replace("{channels}", trackedChannels.toString()),
    });

    await interaction.editReply({ embeds: [embed] });
  },
};

export default ChannelsCommand;
