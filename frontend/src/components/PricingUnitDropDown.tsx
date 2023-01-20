import { Select } from "antd";
// @ts-ignore
import React from "react";
import { UseQueryResult } from "react-query";
import { PricingUnits } from "../api/api";
import { useQuery } from "react-query";
import { CurrencyType } from "../types/pricing-unit-type";

interface PricingUnitDropDownProps {
  defaultValue?: string;
  setCurrentCurrency: (currency: string) => void;
  setCurrentSymbol: (symbol: string) => void;
  shouldShowAllOption?: boolean;
}

const PricingUnitDropDown: React.FC<PricingUnitDropDownProps> = ({
  defaultValue,
  setCurrentCurrency,
  setCurrentSymbol,
  shouldShowAllOption,
}) => {
  const { data, isLoading }: UseQueryResult<CurrencyType[]> = useQuery<
    CurrencyType[]
  >(["pricing_unit_list"], () =>
    PricingUnits.list().then((res) => {
      return res;
    })
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
      defaultValue={defaultValue}
      onChange={(currency: string) => {
        setCurrentCurrency(currency);
        const selectedPricingUnit = data?.find(
          (unit) => unit.code === currency
        );
        if (selectedPricingUnit) {
          setCurrentSymbol(selectedPricingUnit.symbol);
        }
      }}
      options={getCurrencies()?.map((pc) => {
        return { label: `${pc.name} ${pc.symbol}`, value: pc.code };
      })}
    />
  );
};

export default PricingUnitDropDown;
