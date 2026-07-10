import type { JSX } from "react";
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import LightbulbOutlinedIcon from "@mui/icons-material/LightbulbOutlined";
import type { AnalystReport } from "../types";

function Section({ title, body }: { title: string; body: string }): JSX.Element {
  return (
    <Stack spacing={0.5}>
      <Typography variant="subtitle2" color="primary">
        {title}
      </Typography>
      <Typography variant="body2">{body}</Typography>
    </Stack>
  );
}

function BulletList({
  title,
  items,
  icon,
  color,
}: {
  title: string;
  items: string[];
  icon: JSX.Element;
  color: string;
}): JSX.Element | null {
  if (items.length === 0) {
    return null;
  }
  return (
    <Stack spacing={0.5}>
      <Typography variant="subtitle2" color="primary">
        {title}
      </Typography>
      <List dense disablePadding>
        {items.map((item) => (
          <ListItem key={item} disableGutters alignItems="flex-start" sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: 32, mt: "2px", color }}>{icon}</ListItemIcon>
            <ListItemText primary={item} slotProps={{ primary: { variant: "body2" } }} />
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}

export function ReportCard({ report }: { report: AnalystReport }): JSX.Element {
  return (
    <Card>
      <CardHeader title={`${report.ticker} — Analyst Report`} />
      <CardContent>
        <Stack spacing={2.5}>
          <Section title="Executive Summary" body={report.executive_summary} />
          <Section title="Financial Health" body={report.financial_health} />
          <Section title="Valuation" body={report.valuation_assessment} />
          <BulletList
            title="Risk Factors"
            items={report.risk_factors}
            icon={<WarningAmberIcon fontSize="small" />}
            color="warning.main"
          />
          <BulletList
            title="Key Themes"
            items={report.key_themes}
            icon={<LightbulbOutlinedIcon fontSize="small" />}
            color="info.main"
          />
          <Divider />
          <Alert severity="info" variant="outlined">
            {report.disclaimer}
          </Alert>
        </Stack>
      </CardContent>
    </Card>
  );
}
