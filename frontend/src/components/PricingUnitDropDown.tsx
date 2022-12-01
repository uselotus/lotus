import { Select } from "antd";
// @ts-ignore
import React, {useState} from "react";
import {UseQueryResult} from "react-query";
import {PricingUnits} from "../api/api";
import {useQuery} from "react-query";
import {PricingUnit} from "../types/pricing-unit-type";

interface PricingUnitDropDownProps {
    defaultValue?:string,
    setCurrentCurrency:(currency:string) => void
    shouldShowAllOption?:boolean
}


const PricingUnitDropDown:React.FC<PricingUnitDropDownProps> = ({defaultValue, setCurrentCurrency, shouldShowAllOption}) => {
    const {data, isLoading}: UseQueryResult<PricingUnit[]> = useQuery<PricingUnit[]>(
        ["pricing_unit_list"],
        () =>
            PricingUnits.list().then((res) => {
                return res;
            })
    );

    const getCurrencies = () => {
        const items = data || []
        if(shouldShowAllOption) {
            return [
                ...items,
                {
                    code: "All",
                    name: "All Currencies",
                    symbol: ""
                },
            ]
        }
        return items
    }

    return (
        <Select size="small" defaultValue={defaultValue} onChange={setCurrentCurrency} options={getCurrencies()?.map(pc => {
            return {label: `${pc.name}-${pc.symbol}`, value: pc.code}
        })}/>
    );
};

export default PricingUnitDropDown;
