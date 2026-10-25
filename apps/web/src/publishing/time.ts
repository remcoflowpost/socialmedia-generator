/** Datum- en tijdhulpjes in de tijdzone van het bedrijf (niet die van de browser). */

export function fmt(iso: string | null, zone: string, style: "time" | "day" | "full" = "full"): string {
  if (!iso) return "";
  const options: Intl.DateTimeFormatOptions =
    style === "time"
      ? { hour: "2-digit", minute: "2-digit" }
      : style === "day"
        ? { weekday: "short", day: "numeric", month: "short" }
        : { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" };
  return new Intl.DateTimeFormat("nl-NL", { ...options, timeZone: zone }).format(new Date(iso));
}

/** YYYY-MM-DD van een moment in de gegeven zone. */
export function localDate(iso: string | Date, zone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    typeof iso === "string" ? new Date(iso) : iso,
  );
}

export function localTime(iso: string, zone: string): string {
  return new Intl.DateTimeFormat("nl-NL", { timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

/** Maandag van de week van `day` (YYYY-MM-DD), als YYYY-MM-DD. Rekent op kalenderdagen, dus zonder tijdzone-effecten. */
export function mondayOf(day: string): string {
  const d = new Date(`${day}T12:00:00Z`);
  const iso = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - iso);
  return d.toISOString().slice(0, 10);
}

export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export const WEEKDAYS = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"];

export const STATUS_LABEL: Record<string, string> = {
  scheduled: "Gepland",
  publishing: "Wordt verstuurd",
  published: "Gepubliceerd",
  failed: "Mislukt",
  cancelled: "Geannuleerd",
};
