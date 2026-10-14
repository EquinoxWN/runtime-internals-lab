// Command-line entry: node src/churn.js --ops N --window W --seed S --warmup K --rounds R
import { main } from "./cli.js";

process.exitCode = main(
  process.argv.slice(2),
  (line) => console.log(line),
  (line) => console.error(line),
);
