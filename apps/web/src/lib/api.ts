// Public facade: domain modules own endpoints; existing consumers keep this import.
export type * from "./api/types";
export { unwrapList } from "./api/http";
import { dataApi } from "./api/data";
import { strategiesApi } from "./api/strategies";
import { validationApi } from "./api/validation";
import { backtestsApi } from "./api/backtests";
import { codeApi } from "./api/code";
import { researchApi } from "./api/research";
import { universesApi } from "./api/universes";
import { portfoliosApi } from "./api/portfolios";
import { paperApi } from "./api/paper";
import { riskApi } from "./api/risk";
import { healthApi } from "./api/health";

export const api = {
  ...dataApi,
  ...strategiesApi,
  ...validationApi,
  ...backtestsApi,
  ...codeApi,
  ...researchApi,
  ...universesApi,
  ...portfoliosApi,
  ...paperApi,
  ...riskApi,
  ...healthApi,
};
