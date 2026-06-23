import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import styles from "./RichText.module.css";

const INLINE_DISALLOWED_ELEMENTS = [
  "address",
  "article",
  "aside",
  "blockquote",
  "br",
  "caption",
  "div",
  "figcaption",
  "figure",
  "footer",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "header",
  "hr",
  "img",
  "li",
  "ol",
  "p",
  "pre",
  "section",
  "table",
  "tbody",
  "td",
  "tfoot",
  "th",
  "thead",
  "tr",
  "ul"
];

const TEX_COMMAND_NAMES = [
  "backslash",
  "coloneqq",
  "operatorname",
  "rightarrow",
  "subseteq",
  "subset",
  "mathbf",
  "mathbb",
  "mathcal",
  "mathfrak",
  "mathsf",
  "mathit",
  "langle",
  "rangle",
  "ldots",
  "otimes",
  "oplus",
  "colon",
  "cong",
  "dots",
  "infty",
  "leftarrow",
  "mapsto",
  "mathrm",
  "vec",
  "Gamma",
  "Omega",
  "Delta",
  "Sigma",
  "theta",
  "lambda",
  "rho",
  "phi",
  "psi",
  "mu",
  "to",
  "in"
];
const TEX_COMMAND = String.raw`\\(?:${TEX_COMMAND_NAMES.join("|")})(?![A-Za-z])(?:\s*\{[^{}]*\})?`;
const TEX_TOKEN = String.raw`(?:${TEX_COMMAND}|[A-Za-z]|[0-9]+|[{}_^()+\-*/=<>|:.,;[\]])`;
const BARE_TEX_PATTERN = new RegExp(
  String.raw`(^|[\s"'“‘(])((?:[A-Za-z0-9_{}^*()+\-=/<>|:.,;[\]]+\s*)?${TEX_COMMAND}(?:\s*${TEX_TOKEN})*)`,
  "g"
);

interface RichTextProps {
  text?: string;
  inline?: boolean;
  className?: string;
}

export function RichText({ text = "", inline = false, className }: RichTextProps) {
  const source = normalizeMath(text || "");
  const classNames = [styles.richText, inline ? styles.inline : styles.block, className].filter(Boolean).join(" ");
  const markdown = (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      disallowedElements={inline ? INLINE_DISALLOWED_ELEMENTS : ["img"]}
      unwrapDisallowed
      components={
        inline
          ? {
              a: ({ children }) => <>{children}</>
            }
          : undefined
      }
    >
      {source}
    </ReactMarkdown>
  );

  return inline ? <span className={classNames}>{markdown}</span> : <div className={classNames}>{markdown}</div>;
}

function normalizeMath(text: string): string {
  const withDollarDelimiters = text
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, body: string) => `$$${body}$$`)
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_, body: string) => `$${body}$`);
  return normalizeBareTex(withDollarDelimiters);
}

function normalizeBareTex(text: string): string {
  let output = "";
  let index = 0;
  while (index < text.length) {
    const dollarIndex = text.indexOf("$", index);
    if (dollarIndex === -1) {
      output += wrapBareTex(text.slice(index));
      break;
    }
    output += wrapBareTex(text.slice(index, dollarIndex));
    const delimiter = text.startsWith("$$", dollarIndex) ? "$$" : "$";
    const endIndex = text.indexOf(delimiter, dollarIndex + delimiter.length);
    if (endIndex === -1) {
      output += text.slice(dollarIndex);
      break;
    }
    output += text.slice(dollarIndex, endIndex + delimiter.length);
    index = endIndex + delimiter.length;
  }
  return output;
}

function wrapBareTex(text: string): string {
  return text.replace(BARE_TEX_PATTERN, (_match, prefix: string, expression: string) => `${prefix}$${expression.trim()}$`);
}
