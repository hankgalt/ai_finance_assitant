"""Identity contracts that preserve portfolio ownership relationships."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ai_finance_assistant.contracts.common import CurrencyCode, Identifier


class SecurityIdentifierType(StrEnum):
    TICKER = "ticker"
    CUSIP = "cusip"
    ISIN = "isin"
    USER_DEFINED = "user_defined"


class SecurityIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_type: SecurityIdentifierType
    value: str = Field(min_length=1, max_length=64)


class PortfolioIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    portfolio_id: Identifier
    base_currency: CurrencyCode


class AccountIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_id: Identifier
    portfolio_id: Identifier
    account_type: str = Field(min_length=1, max_length=64)


class HoldingIdentifier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    holding_id: Identifier
    account_id: Identifier
    security: SecurityIdentifier
