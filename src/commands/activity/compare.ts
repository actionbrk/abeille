import { InteractionContextType, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getTrend } from "../../database/bee-database";
import { type ChartConfiguration } from "chart.js";
import { ChartJSNodeCanvas, type ChartCallback } from "chartjs-node-canvas";
import logger from "../../logger";
import { format } from "date-fns";
import { enUS } from "date-fns/locale";
import pl from "nodejs-polars";
import sharp from "sharp";

const translations = LocaleHelper.getCommandTranslations("compare");

const chartCallback: ChartCallback = (ChartJS) => {
  ChartJS.defaults.responsive = false;
  ChartJS.defaults.maintainAspectRatio = false;
};

const chartJSNodeCanvas = new ChartJSNodeCanvas({
  width: 700,
  height: 500,
  backgroundColour: "#111111",
  chartCallback,
  plugins: {
    globalVariableLegacy: ["chartjs-adapter-date-fns"],
  },
});

const CompareCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("compare")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Compare usage trends between two expressions.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addStringOption((option) =>
      option
        .setName("expression1")
        .setNameLocalizations(translations.options!.expression1!.localizedNames)
        .setDescription("First expression to compare.")
        .setDescriptionLocalizations(translations.options!.expression1!.localizedDescriptions)
        .setRequired(true)
        .setMinLength(3)
        .setMaxLength(50)
    )
    .addStringOption((option) =>
      option
        .setName("expression2")
        .setNameLocalizations(translations.options!.expression2!.localizedNames)
        .setDescription("Second expression to compare.")
        .setDescriptionLocalizations(translations.options!.expression2!.localizedDescriptions)
        .setRequired(true)
        .setMinLength(3)
        .setMaxLength(50)
    )
    .addIntegerOption((option) =>
      option
        .setName("period")
        .setNameLocalizations(translations.options!.period!.localizedNames)
        .setDescription("Time period for comparison.")
        .setDescriptionLocalizations(translations.options!.period!.localizedDescriptions)
        .setRequired(true)
        .addChoices(
          {
            name: "6 months",
            name_localizations: translations.options?.period?.choices?.sixMonths?.localizedNames,
            value: 182,
          },
          {
            name: "1 year",
            name_localizations: translations.options?.period?.choices?.oneYear?.localizedNames,
            value: 365,
          },
          {
            name: "2 years",
            name_localizations: translations.options?.period?.choices?.twoYears?.localizedNames,
            value: 730,
          },
          {
            name: "3 years",
            name_localizations: translations.options?.period?.choices?.threeYears?.localizedNames,
            value: 1096,
          },
          {
            name: "Since the beginning",
            name_localizations: translations.options?.period?.choices?.beginning?.localizedNames,
            value: 9999,
          }
        )
    ),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const expression1 = interaction.options.getString("expression1", true);
    const expression2 = interaction.options.getString("expression2", true);
    const period = interaction.options.getInteger("period", true);
    const userLocale: string = interaction.locale;
    const serverName = interaction.guild?.name ?? "Unknown Server";
    const botName = `${interaction.client.user?.username ?? ""}#${interaction.client.user?.discriminator ?? ""}`;

    const fileBuffer = await plotCompare(guildId, expression1, expression2, period, userLocale, serverName, botName);

    await interaction.editReply({
      files: [
        {
          attachment: fileBuffer,
          name: "abeille.webp",
          contentType: "image/webp",
        },
      ],
    });
  },
};

async function plotCompare(
  guildId: string,
  expression1: string,
  expression2: string,
  period: number,
  userLocale: string,
  serverName: string,
  botName: string
): Promise<Buffer<ArrayBufferLike>> {
  const trend1Results = getTrend(guildId, expression1);
  const trend2Results = getTrend(guildId, expression2);

  logger.debug("Trend results for %s: %o", expression1, trend1Results);
  logger.debug("Trend results for %s: %o", expression2, trend2Results);

  const trend1Map = new Map(trend1Results.trend.map((t) => [t.date, t.messages ?? 0]));
  const trend2Map = new Map(trend2Results.trend.map((t) => [t.date, t.messages ?? 0]));

  const endDate = trend1Results.guildLastMessageDate ?? new Date();
  const startDate =
    period === 9999
      ? trend1Results.guildFirstMessageDate ?? new Date()
      : new Date(endDate.getTime() - period * 24 * 60 * 60 * 1000);

  const trends1: { x: string; y: number }[] = [];
  const trends2: { x: string; y: number }[] = [];

  let date = new Date(startDate);
  while (date <= endDate) {
    const dateAsStr = format(date, "yyyy-MM-dd");
    trends1.push({ x: dateAsStr, y: trend1Map.get(dateAsStr) || 0 });
    trends2.push({ x: dateAsStr, y: trend2Map.get(dateAsStr) || 0 });
    date = new Date(date.getTime() + 24 * 60 * 60 * 1000);
  }

  let dataFrame1 = pl.DataFrame(trends1);
  let dataFrame2 = pl.DataFrame(trends2);

  dataFrame1 = dataFrame1
    .withColumn(pl.col("x").cast(pl.Date))
    .withColumn(pl.col("y").rollingMean({ windowSize: 14 }).fillNull(0));
  dataFrame2 = dataFrame2
    .withColumn(pl.col("x").cast(pl.Date))
    .withColumn(pl.col("y").rollingMean({ windowSize: 14 }).fillNull(0));

  // Dynamically load the locale based on the user's locale
  let locale = (await import("date-fns/locale/" + userLocale))[userLocale.replace("-", "")];
  if (!locale) {
    locale = enUS;
  }

  const dataFrameObject1 = dataFrame1.toRecords();
  const dataFrameObject2 = dataFrame2.toRecords();

  const chartConfiguration: ChartConfiguration<"line", { x: Date; y: number }[]> = {
    type: "line",
    data: {
      datasets: [
        {
          label: expression1,
          data: dataFrameObject1 as unknown as { x: Date; y: number }[],
          borderWidth: 3,
          borderColor: "rgb(255, 255, 0)",
          backgroundColor: "rgba(255, 255, 0, 0.1)",
          fill: true,
          normalized: true,
        },
        {
          label: expression2,
          data: dataFrameObject2 as unknown as { x: Date; y: number }[],
          borderWidth: 3,
          borderColor: "rgb(69, 133, 230)",
          backgroundColor: "rgba(69, 133, 230, 0.1)",
          fill: true,
          normalized: true,
        },
      ],
    },
    options: {
      animation: false,
      responsive: false,
      devicePixelRatio: 2,
      datasets: {
        line: {
          borderWidth: 2,
          pointStyle: false,
          cubicInterpolationMode: "default",
          borderJoinStyle: "round",
        },
      },
      layout: {
        padding: {
          top: 10,
          bottom: 15,
          right: 25,
          left: 25,
        },
      },
      locale: userLocale,
      scales: {
        y: {
          type: "linear",
          alignToPixels: true,
          border: {
            display: false,
          },
          beginAtZero: true,
          min: 0,
          ticks: {
            callback: function (value) {
              const intValue = parseFloat(value.toString());
              return (100 * intValue).toFixed(2) + "%";
            },
            color: "white",
            autoSkip: true,
          },
          grid: {
            color: "rgb(88, 88, 88)",
          },
        },
        x: {
          type: "time",
          alignToPixels: true,
          border: {
            display: false,
          },
          ticks: {
            color: "white",
            autoSkip: true,
            maxRotation: 0,
            major: { enabled: true },
          },
          adapters: {
            date: {
              locale: locale,
            },
          },
          grid: {
            color: "rgb(88, 88, 88)",
          },
          title: {
            display: true,
            text: (translations.responses?.graphFooter?.[userLocale] ?? "Generated on {date} by {botName}")
              .replace("{date}", new Date().toLocaleString(userLocale, { dateStyle: "short" }))
              .replace("{botName}", botName),
            color: "white",
            align: "end",
            padding: { top: 10 },
            font: {
              size: 10,
            },
          },
        },
      },
      plugins: {
        colors: {
          enabled: true,
        },
        title: {
          text: (translations.responses?.graphTitle?.[userLocale] ?? "'{expression1}' vs '{expression2}'")
            .replace("{expression1}", expression1)
            .replace("{expression2}", expression2),
          font: {
            size: 18,
            weight: "bold",
          },
          display: true,
          align: "start",
          color: "white",
        },
        subtitle: {
          text: (translations.responses?.graphSubTitle?.[userLocale] ?? "On {serverName}").replace(
            "{serverName}",
            serverName
          ),
          display: true,
          align: "start",
          padding: { bottom: 25 },
          color: "white",
          font: {
            style: "italic",
          },
        },
        legend: {
          display: true,
          position: "top",
          labels: {
            color: "white",
          },
        },
      },
    },
  };

  const buffer = await chartJSNodeCanvas.renderToBuffer(chartConfiguration as unknown as ChartConfiguration);
  return sharp(buffer).toFormat("webp", { quality: 80 }).toBuffer();
}

export default CompareCommand;
