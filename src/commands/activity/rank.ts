import {
  ButtonBuilder,
  ButtonStyle,
  ComponentType,
  EmbedBuilder,
  InteractionContextType,
  SlashCommandBuilder,
  userMention,
} from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import logger from "../../logger";
import { getRank } from "../../database/bee-database";
import { HashHelper } from "../../utils/hash-helper";

const translations = LocaleHelper.getCommandTranslations("rank");

const RankCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("rank")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Your rank in the use of an expression.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addStringOption((option) =>
      option
        .setName("expression")
        .setNameLocalizations(translations.options!.expression!.localizedNames)
        .setDescription("Enter a word or phrase.")
        .setDescriptionLocalizations(translations.options!.expression!.localizedDescriptions)
        .setRequired(true)
        .setMinLength(3)
        .setMaxLength(200)
    ),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const expression = interaction.options.getString("expression", true);
    const userLocale: string = interaction.locale;

    const authorizedUserIds = new Set<string>([interaction.user.id]);

    const embed = await computeRankForExpression(guildId, expression, userLocale, authorizedUserIds);

    const displayMyRankTranslation = translations.responses?.displayMyRank?.[userLocale] ?? "Display my rank";
    const displayMyRankButton = new ButtonBuilder()
      .setCustomId("display-my-rank")
      .setLabel(displayMyRankTranslation)
      .setStyle(ButtonStyle.Primary)
      .setEmoji("📊");

    const message = await interaction.editReply({
      embeds: [embed],
      components: [
        {
          type: ComponentType.ActionRow,
          components: [displayMyRankButton],
        },
      ],
    });

    const collector = message.createMessageComponentCollector({
      componentType: ComponentType.Button,
      time: 10 * 60 * 1000,
    });

    collector.on("collect", async (i) => {
      const userId = i.user.id;
      if (authorizedUserIds.has(userId)) {
        return i.deferUpdate();
      }
      authorizedUserIds.add(userId);

      const deferUpdatePromise = i.update({ content: "" });

      const editedEmbed = await computeRankForExpression(guildId, expression, userLocale, authorizedUserIds);
      await deferUpdatePromise;
      await i.editReply({
        embeds: [editedEmbed],
      });
    });

    collector.on("end", async () => {
      logger.debug("Collector ended");
      await interaction.editReply({
        components: [],
      });
    });
  },
};

export default RankCommand;

async function computeRankForExpression(
  guildId: string,
  expression: string,
  userLocale: string,
  displayedUsersIds: Set<string>
): Promise<EmbedBuilder> {
  const rankResult = getRank(guildId, expression);

  if (rankResult.length === 0) {
    const embedTitle =
      translations.responses?.rankNone?.[userLocale] ??
      "The expression *{expression}* has never been used on this server.";
    return new EmbedBuilder().setTitle(embedTitle.replace("{expression}", expression)).setColor(0xff0000);
  } else {
    const totalCount = rankResult.reduce((acc, result) => acc + result.count, 0);

    const hashMapOfUserId = new Map<string, string>();
    displayedUsersIds.forEach((userId) => {
      const userIdHash = HashHelper.computeHash(userId);
      hashMapOfUserId.set(userIdHash, userId);
    });

    // Show top 10 AND already displayed users
    let embedDescription = rankResult
      .filter((result) => result.rank <= 10 || displayedUsersIds.has(result.author_id))
      .map((result) => {
        let userName;
        // 128 means hashed user ID
        if (result.author_id.length === 128) {
          const realUserId = hashMapOfUserId.get(result.author_id);
          if (realUserId) {
            userName = userMention(realUserId);
          } else {
            userName = translations.responses?.unregisteredUser?.[userLocale] ?? "Unregistered user";
          }
        } else {
          userName = userMention(result.author_id);
        }

        const userRank = result.rank;
        const userCount = result.count;
        const userPercentage = ((userCount / totalCount) * 100).toFixed(2);

        const rankIcon = userRank === 1 ? "🥇" : userRank === 2 ? "🥈" : userRank === 3 ? "🥉" : ` ${userRank}.`;
        return `${rankIcon} ${userName} (${userPercentage}%)`;
      })
      .join("\n");

    const embedTitle = (
      translations.responses?.rankFound?.[userLocale] ??
      "`{number}` members have already used the expression *{expression}*"
    )
      .replace("{number}", rankResult.length.toString())
      .replace("{expression}", expression);

    // Displayed users who never used the expression
    const userWhoNeverUsedIt = Array.from(displayedUsersIds).filter((userId) => {
      const userIdHash = HashHelper.computeHash(userId);
      return !rankResult.some((result) => result.author_id === userIdHash || result.author_id === userId);
    });

    if (userWhoNeverUsedIt.length > 0) {
      const neverUsedTranslation =
        translations.responses?.neverUseExpression?.[userLocale] ?? "Have never used this expression";
      const neverUsedList = userWhoNeverUsedIt.map((userId) => userMention(userId)).join("\n");
      embedDescription += `\n\n**${neverUsedTranslation}**\n${neverUsedList}`;
    }

    const embedFooterText =
      translations.responses?.totalExpressionUses?.[userLocale] ??
      "Expression {expression} has been used {count} times";

    return new EmbedBuilder()
      .setTitle(embedTitle)
      .setDescription(embedDescription)
      .setFooter({
        text: embedFooterText.replace("{expression}", expression).replace("{count}", totalCount.toString()),
      })
      .setColor(0xffff00);
  }
}
