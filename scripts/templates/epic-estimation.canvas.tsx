import type { CanvasHostTheme } from "cursor/canvas";
import {
  Card,
  CardBody,
  CardHeader,
  Divider,
  H1,
  H2,
  H3,
  Link,
  Row,
  Stack,
  Text,
  useHostTheme,
} from "cursor/canvas";

const EPIC_DATA = __EPIC_DATA_PLACEHOLDER__;

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const [y, m, d] = v.slice(0, 10).split("-");
  if (!y || !m || !d) return v;
  return `${d}-${m}-${y}`;
}

function fmtDisplayDate(v: string | null | undefined): string {
  return fmtDate(v);
}

function deliveryWindowCaption(
  start: string | null | undefined,
  end: string | null | undefined,
): string | null {
  if (!start || !end) return null;
  const a = new Date(`${start}T12:00:00`).getTime();
  const b = new Date(`${end}T12:00:00`).getTime();
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  const days = Math.round((b - a) / 86_400_000) + 1;
  return `${days} calendar day${days === 1 ? "" : "s"} in delivery window`;
}

function DateBlock({
  label,
  date,
  theme,
}: {
  label: string;
  date: string;
  theme: CanvasHostTheme;
}) {
  return (
    <Stack
      gap={4}
      style={{
        flex: "1 1 160px",
        padding: "12px 14px",
        background: theme.bg.elevated,
        borderRadius: 6,
        border: `1px solid ${theme.stroke.tertiary}`,
        borderLeft: `3px solid ${theme.accent.primary}`,
      }}
    >
      <Text
        size="small"
        tone="tertiary"
        weight="semibold"
        style={{ letterSpacing: "0.05em", textTransform: "uppercase" }}
      >
        {label}
      </Text>
      <Text weight="semibold" style={{ fontSize: 20, lineHeight: 1.25 }}>
        {date}
      </Text>
    </Stack>
  );
}

function fmtNum(v: number | null | undefined): string {
  if (v == null) return "—";
  return String(v);
}

function fmtCalcDays(v: number | null | undefined): string {
  if (v == null) return "—";
  const rounded = Math.round(v * 100) / 100;
  if (Number.isInteger(rounded)) return String(rounded);
  return rounded.toFixed(2).replace(/\.?0+$/, "");
}

function platformDeliveryTitle(platform: string): string {
  if (platform === "Backend") return "Backend Delivery";
  if (platform === "Web") return "Web Delivery";
  if (platform === "Mobile") return "App Delivery";
  return `${platform} Delivery`;
}

function issueLink(key: string): string {
  const base = EPIC_DATA.jiraSiteUrl.replace(/\/$/, "");
  return base ? `${base}/browse/${key}` : `#${key}`;
}

function ColumnStripeTable({
  headers,
  rows,
  theme,
}: {
  headers: string[];
  rows: (string | number | null | undefined)[][];
  theme: CanvasHostTheme;
}) {
  const cellPad = "8px 12px";

  return (
    <div
      style={{
        border: `1px solid ${theme.stroke.tertiary}`,
        borderRadius: 6,
        overflow: "auto",
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 14,
          lineHeight: "20px",
          color: theme.text.primary,
        }}
      >
        <colgroup>
          {headers.map((_, index) => (
            <col
              key={index}
              style={{
                background: index % 2 === 0 ? theme.fill.tertiary : undefined,
              }}
            />
          ))}
        </colgroup>
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th
                key={index}
                style={{
                  textAlign: "left",
                  padding: cellPad,
                  borderBottom: `1px solid ${theme.stroke.tertiary}`,
                  fontWeight: 590,
                  color: theme.text.primary,
                }}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((_, colIndex) => (
                <td
                  key={colIndex}
                  style={{
                    textAlign: "left",
                    padding: cellPad,
                    borderBottom:
                      rowIndex < rows.length - 1
                        ? `1px solid ${theme.stroke.tertiary}`
                        : undefined,
                  }}
                >
                  {row[colIndex] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function EpicEstimationCanvas() {
  const theme = useHostTheme();
  const d = EPIC_DATA;
  const windowCaption = deliveryWindowCaption(d.deliveryStart, d.goLive);

  return (
    <Stack gap={24} style={{ padding: 24, color: theme.text.primary }}>
      <Card>
        <CardBody style={{ padding: 20 }}>
          <Stack gap={16}>
            <Stack gap={6}>
              <Row gap={10} align="center" wrap>
                <H1 style={{ margin: 0 }}>Epic estimation</H1>
                <Text tone="tertiary">·</Text>
                {d.epicUrl ? (
                  <Link href={d.epicUrl}>
                    <Text weight="semibold">{d.epicKey}</Text>
                  </Link>
                ) : (
                  <Text weight="semibold">{d.epicKey}</Text>
                )}
              </Row>
              <Text tone="secondary">{d.prdName}</Text>
            </Stack>

            <Divider />

            <Stack gap={10}>
              <Text
                size="small"
                tone="tertiary"
                weight="semibold"
                style={{ letterSpacing: "0.06em", textTransform: "uppercase" }}
              >
                Delivery window
              </Text>
              <Row gap={12} align="stretch" wrap>
                <DateBlock
                  label="Delivery start"
                  date={fmtDisplayDate(d.deliveryStart)}
                  theme={theme}
                />
                <Text tone="tertiary" weight="semibold" style={{ alignSelf: "center" }}>
                  →
                </Text>
                <DateBlock
                  label="Delivery end"
                  date={fmtDisplayDate(d.goLive)}
                  theme={theme}
                />
              </Row>
              {windowCaption ? (
                <Text size="small" tone="tertiary">
                  {windowCaption}
                </Text>
              ) : null}
            </Stack>
          </Stack>
        </CardBody>
      </Card>

      {d.teamsPlan.length > 0 ? (
        <Card>
          <CardHeader>Teams plan</CardHeader>
          <CardBody style={{ padding: 0 }}>
            <ColumnStripeTable
              theme={theme}
              headers={["Team", "Peak resources", "Effort (h)", "Leave (h)", "Tasks"]}
              rows={d.teamsPlan.map((r) => [
                r.team,
                fmtNum(r.peakResources),
                fmtNum(r.totalEffortHours),
                fmtNum(r.leaveHours || null),
                String(r.taskCount),
              ])}
            />
          </CardBody>
        </Card>
      ) : null}

      {d.platforms.map((plat) => (
        <Card>
          <CardHeader>{platformDeliveryTitle(plat.platform)}</CardHeader>
          <CardBody style={{ padding: 0 }}>
            <ColumnStripeTable
              theme={theme}
              headers={[
                "Stage",
                "Resources",
                "Effort (h)",
                "Leave (h)",
                "Calc days",
                "Start",
                "End",
              ]}
              rows={plat.stages.map((s) => [
                s.synthetic ? `${s.stage} (est.)` : s.stage,
                fmtNum(s.resources),
                fmtNum(s.effortsHours),
                fmtNum(s.leaveHours || null),
                fmtCalcDays(s.calculatedDays),
                fmtDate(s.start),
                fmtDate(s.end),
              ])}
            />
          </CardBody>
        </Card>
      ))}

      {d.members.length > 0 ? (
        <Card>
          <CardHeader>Member breakdown</CardHeader>
          <CardBody style={{ padding: 0 }}>
            <ColumnStripeTable
              theme={theme}
              headers={["Team", "Member", "Effort (h)", "Leave (h)", "Calc days", "Mapped tasks"]}
              rows={d.members.map((m) => [
                m.team,
                m.member ?? "—",
                fmtNum(m.effortsHours),
                fmtNum(m.leaveHours > 0 ? m.leaveHours : null),
                fmtCalcDays(m.calculatedDays),
                (m.tasks ?? []).join(", ") || "—",
              ])}
            />
          </CardBody>
        </Card>
      ) : null}

      {d.unmapped.length > 0 ? (
        <Stack gap={8}>
          <H2>Unmapped work</H2>
          {d.unmapped.map((u) => (
            <Text>
              <Link href={issueLink(u.key)}>{u.key}</Link>: {u.summary} ({u.effortsHours}h)
            </Text>
          ))}
        </Stack>
      ) : null}

      {d.dataQuality.length > 0 ? (
        <Stack gap={8}>
          <H3>Data quality</H3>
          {d.dataQuality.map((row) => (
            <Text>
              {row.member} · <Link href={issueLink(row.key)}>{row.key}</Link> · {row.reason}
            </Text>
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
