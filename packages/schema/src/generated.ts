/* Gegenereerd uit apps/api/app/schema via scripts/export_schema.py. Niet handmatig aanpassen. */

export interface FlowSocialSchema {
  BrandKitData?: BrandKitData;
  FormatsConfig?: FormatsConfig;
  LayoutReport?: LayoutReport;
  PostDocument?: PostDocument;
  RenderInput?: RenderInput;
  TemplateDefinition?: TemplateDefinition;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandKitData".
 */
export interface BrandKitData {
  colors: BrandColors;
  fonts: BrandFonts;
  locks: ("logo" | "colors" | "fonts" | "style_anchor")[];
  logos: BrandLogos;
  negativePrompt: string;
  styleAnchor: StyleAnchor;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandColors".
 */
export interface BrandColors {
  accent: string;
  primary: string;
  secondary: string;
  textOnDark: string;
  textOnLight: string;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandFonts".
 */
export interface BrandFonts {
  body: BrandFont;
  heading: BrandFont;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandFont".
 */
export interface BrandFont {
  fallback: string;
  family: string;
  files: BrandFontFile[];
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandFontFile".
 */
export interface BrandFontFile {
  assetId: string;
  style: "normal" | "italic";
  weight: number;
}
/**
 * Asset-id's. light = lichte variant voor donkere achtergronden.
 */
export interface BrandLogos {
  logoDark: string | null;
  logoIcon: string | null;
  logoLight: string | null;
}
export interface StyleAnchor {
  description: string;
  /**
   * @maxItems 6
   */
  referenceAssetIds: string[];
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "FormatsConfig".
 */
export interface FormatsConfig {
  formats: Format[];
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "Format".
 */
export interface Format {
  exports: ("jpeg" | "png" | "mp4")[];
  height: number;
  id: string;
  label: string;
  layoutClass: string;
  platform: string;
  safeZone: SafeZone;
  width: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "SafeZone".
 */
export interface SafeZone {
  bottom: number;
  left: number;
  right: number;
  top: number;
}
/**
 * Uitkomst van de layout-engine (TypeScript) voor een formaat.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "LayoutReport".
 */
export interface LayoutReport {
  formatKey: string;
  height: number;
  issues: QualityIssue[];
  layers: LayerReport[];
  width: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "QualityIssue".
 */
export interface QualityIssue {
  code:
    | "missing_required_field"
    | "missing_asset"
    | "resolution_low"
    | "resolution_too_low"
    | "outside_safe_zone"
    | "text_overflow"
    | "contrast_low"
    | "embargo_active"
    | "font_missing";
  details: {
    [k: string]: unknown;
  };
  formatKey: string | null;
  layerId: string | null;
  message: string;
  severity: "warning" | "error";
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "LayerReport".
 */
export interface LayerReport {
  box: PixelBox;
  color: string | null;
  fontSize: number | null;
  hidden: boolean;
  id: string;
  lines: string[] | null;
  sourceScale: number | null;
  type: string;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "PixelBox".
 */
export interface PixelBox {
  height: number;
  width: number;
  x: number;
  y: number;
}
/**
 * Het bewerkbare deel van een post: ingevulde velden en per-laag overrides.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "PostDocument".
 */
export interface PostDocument {
  content: {
    [k: string]: string | string[] | null;
  };
  overrides: {
    [k: string]: LayerOverride;
  };
}
/**
 * Afwijking per laag voor een post. Alleen toegestaan op lagen die editable zijn en
 * niet onder een brand-kit-lock vallen.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "LayerOverride".
 */
export interface LayerOverride {
  assetId: string | null;
  focus: Point | null;
  hidden: boolean | null;
}
/**
 * Focuspunt, 0..1 over breedte en hoogte van het bronbeeld.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "Point".
 */
export interface Point {
  x: number;
  y: number;
}
/**
 * Alles wat de compositie nodig heeft om een formaat te renderen.
 *
 * De render-service en de browser-preview krijgen precies dit document, zodat preview en
 * export dezelfde bron hebben.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "RenderInput".
 */
export interface RenderInput {
  assets: {
    [k: string]: RenderAsset;
  };
  brand: BrandKitData;
  format: Format;
  options: RenderOptions;
  post: PostDocument;
  template: TemplateDefinition;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "RenderAsset".
 */
export interface RenderAsset {
  height: number | null;
  mime: string;
  src: string;
  width: number | null;
}
export interface RenderOptions {
  hideText: boolean;
  showSafeZones: boolean;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "TemplateDefinition".
 */
export interface TemplateDefinition {
  description: string;
  fields: ContentField[];
  formats: string[] | null;
  key: string;
  layers: Layer[];
  name: string;
  type: string;
  version: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "ContentField".
 */
export interface ContentField {
  help: string | null;
  key: string;
  label: string;
  maxLength: number | null;
  minWidth: number | null;
  options: string[];
  required: boolean;
  type: "text" | "longtext" | "image" | "select" | "multiselect" | "date";
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "Layer".
 */
export interface Layer {
  brandAsset: ("logo_light" | "logo_dark" | "logo_icon") | null;
  editable: boolean;
  field: string | null;
  id: string;
  layouts: {
    [k: string]: LayerLayout;
  };
  prompt: PromptSpec | null;
  shapeStyle: ShapeStyle | null;
  source: "upload" | "brand_asset" | "generated" | "content_field" | "static";
  static: string | null;
  textStyle: TextStyle | null;
  type: "background" | "image" | "element" | "logo" | "text" | "shape" | "video";
  z: number;
}
/**
 * Layout voor een formaat. Alle velden optioneel, zodat overrides alleen afwijkingen
 * hoeven op te geven. Volgorde van samenvoegen: default, layout_class, formaatsleutel.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "LayerLayout".
 */
export interface LayerLayout {
  align: ("left" | "center" | "right") | null;
  box: Box | null;
  fit: ("cover" | "contain") | null;
  focus: Point | null;
  hidden: boolean | null;
  maxFontSize: number | null;
  maxLines: number | null;
  minFontSize: number | null;
  verticalAlign: ("top" | "center" | "bottom") | null;
}
/**
 * Positie en grootte in procenten van de safe area (of het canvas bij bleed).
 *
 * x en y zijn offsets vanaf het anker naar binnen; bij anker "center" schuiven ze
 * het midden op.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "Box".
 */
export interface Box {
  anchor: "top-left" | "top" | "top-right" | "left" | "center" | "right" | "bottom-left" | "bottom" | "bottom-right";
  bleed: boolean;
  height: number;
  width: number;
  x: number;
  y: number;
}
/**
 * Generatie-instructie per laag. Wordt in fase 2 gebruikt, staat er nu al in zodat
 * templates niet opnieuw hoeven te worden opgezet.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "PromptSpec".
 */
export interface PromptSpec {
  base: string;
  inheritBrandStyle: boolean;
  kind: "image" | "video" | "element";
  masterAspect: string;
  model: string | null;
  negative: string;
  provider: string;
  seed: number | null;
  useBrandReferences: boolean;
  variables: string[];
  variants: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "ShapeStyle".
 */
export interface ShapeStyle {
  fill: string | null;
  gradient: Gradient | null;
  opacity: number;
  radius: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "Gradient".
 */
export interface Gradient {
  angle: number;
  fromColor: string;
  fromOpacity: number;
  toColor: string;
  toOpacity: number;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "TextStyle".
 */
export interface TextStyle {
  color: string;
  font: "heading" | "body";
  letterSpacing: number;
  lineHeight: number;
  uppercase: boolean;
  weight: number;
}
/**
 * Asset-id's. light = lichte variant voor donkere achtergronden.
 *
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "BrandLogos".
 */
export interface BrandLogos1 {
  logoDark: string | null;
  logoIcon: string | null;
  logoLight: string | null;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "RenderOptions".
 */
export interface RenderOptions1 {
  hideText: boolean;
  showSafeZones: boolean;
}
/**
 * This interface was referenced by `FlowSocialSchema`'s JSON-Schema
 * via the `definition` "StyleAnchor".
 */
export interface StyleAnchor1 {
  description: string;
  /**
   * @maxItems 6
   */
  referenceAssetIds: string[];
}
