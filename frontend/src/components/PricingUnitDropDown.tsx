import { Select } from "antd";
import React from "react";
import { UseQueryResult, useQuery } from "react-query";
import { PricingUnits } from "../api/api";
import { CurrencyType } from "../types/pricing-unit-type";

interface PricingUnitDropDownProps {
  defaultValue?: string;
  setCurrentCurrency: (currency: string) => void;
  setCurrentSymbol?: (symbol: string) => void;
  shouldShowAllOption?: boolean;
  disabled?: boolean;
}

const PricingUnitDropDown: React.FC<PricingUnitDropDownProps> = ({
  defaultValue,
  setCurrentCurrency,
  setCurrentSymbol,
  shouldShowAllOption,
  disabled = false,
}) => {
  const { data }: UseQueryResult<CurrencyType[]> = useQuery<CurrencyType[]>(
    ["pricing_unit_list"],
    () => PricingUnits.list().then((res) => res)
  );

  const getCurrencies = () => {
    const items = data || [];
    if (shouldShowAllOption) {
      return [
        ...items,
        {
          code: "All",
          name: "All Currencies",
          symbol: "",
        },
      ];
    }
    return items;
  };

  return (
    <Select
      size="small"
      disabled={disabled}
      defaultValue={defaultValue}
      onChange={(currency: string) => {
        setCurrentCurrency(currency);
        const selectedPricingUnit = data?.find(
          (unit) => unit.code === currency
        );
        if (selectedPricingUnit && setCurrentSymbol) {
          setCurrentSymbol(selectedPricingUnit.symbol);
        }
      }}
      options={getCurrencies()?.map((pc) => ({
        label: `${pc.name} ${pc.symbol}`,
        value: pc.code,
      }))}
    />
  );
};

export default PricingUnitDropDown;
