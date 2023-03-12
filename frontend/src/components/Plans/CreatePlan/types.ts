import { FeatureType } from "./../../../types/feature-type";
import React from "react";
import { FormInstance } from "antd";
import { CurrencyType } from "../../../types/pricing-unit-type";
import { CreateComponent, PlanType } from "../../../types/plan-type";

interface BillingType {
  name: string;
  label: string;
}

export interface StepProps {
  form: FormInstance<any>;

  allPlans: PlanType[];
  setAllPlans: React.Dispatch<React.SetStateAction<PlanType[]>>;

  availableBillingTypes: BillingType[];
  setAvailableBillingTypes: React.Dispatch<React.SetStateAction<BillingType[]>>;

  month: number;
  setMonth: React.Dispatch<React.SetStateAction<number>>;

  allCurrencies: CurrencyType[];
  setAllCurrencies: React.Dispatch<React.SetStateAction<CurrencyType[]>>;

  selectedCurrency: CurrencyType;
  setSelectedCurrency: React.Dispatch<React.SetStateAction<CurrencyType>>;

  priceAdjustmentType: string;
  setPriceAdjustmentType: React.Dispatch<React.SetStateAction<string>>;

  planFeatures: FeatureType[];
  editFeatures: (feature_name: string) => void;
  removeFeature: (feature_id: string) => void;

  showFeatureModal: () => void;

  componentsData: CreateComponent[];
  handleComponentEdit: (component_id: string) => void;
  deleteComponent: (component_id: string) => void;

  showComponentModal: () => void;

  setExternalLinks: (links: string[]) => void;
}
