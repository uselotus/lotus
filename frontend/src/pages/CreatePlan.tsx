/* eslint-disable no-shadow */
/* eslint-disable camelcase */
/* eslint-disable no-plusplus */
import { Button, Col, Form, Modal, Row } from "antd";
// @ts-ignore
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";
import clsx from "clsx";
import UsageComponentForm from "../components/Plans/UsageComponentForm";

import {
  CreateComponent,
  PlanType,
  CreateRecurringCharge,
  CreatePlanRequestType,
  CreateComponentRequestType,
} from "../types/plan-type";
import { Plan, Organization } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { PageLayout } from "../components/base/PageLayout";
import { CurrencyType } from "../types/pricing-unit-type";
import PlanInformation, {
  validate as validatePlanInformation,
} from "../components/Plans/CreatePlan/PlanInformation";
import VersionInformation, {
  validate as validateVersionInformation,
} from "../components/Plans/CreatePlan/VersionInformation";
import ChargesAndFeatures, {
  validate as validateChargesAndFeatures,
} from "../components/Plans/CreatePlan/ChargesAndFeatures";
import BreadCrumbs from "../components/BreadCrumbs";
import RecurringChargeForm from "../components/Plans/RecurringChargeForm";
import { components } from "../gen-types";

interface ComponentDisplay {
  metric: string;
  cost_per_batch: number;
  metric_units_per_batch: number;
  free_metric_units: number;
  max_metric_units: number;
  id: number;
}

const durationConversion = {
  monthly: "Month",
  quarterly: "Quarter",
  yearly: "Year",
};

function CreatePlan() {
  const [showRecurringChargeModal, setShowRecurringChargeModal] =
    useState<boolean>(false);
  const [isCurrentStepValid, setIsCurrentStepValid] = useState<boolean>(false);
  const [showCreateCustomPlanModal, setShowCreateCustomPlanModal] =
    useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [allCurrencies, setAllCurrencies] = useState<CurrencyType[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState<CurrencyType | null>(
    null
  );
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [priceAdjustmentType, setPriceAdjustmentType] =
    useState<string>("none");
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<CreateComponent[]>([]);
  const [form] = Form.useForm();
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);
  const [recurringCharges, setRecurringCharges] = useState<
    components["schemas"]["PlanDetail"]["versions"][0]["recurring_charges"]
  >([]);
  const [month, setMonth] = useState(1);
  const [editComponentItem, setEditComponentsItem] =
    useState<CreateComponent>();
  const [availableBillingTypes, setAvailableBillingTypes] = useState<
    { name: string; label: string }[]
  >([{ label: "Monthly", name: "monthly" }]);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!allPlans?.length) {
      Plan.getPlans().then((data) => setAllPlans(data));
    }
  }, []);

  useEffect(() => {
    if (!allCurrencies?.length) {
      Organization.get().then((res) => {
        setAllCurrencies(res[0].available_currencies);
        setSelectedCurrency(res[0].default_currency);
        if (res[0].default_currency) {
          form.setFieldsValue({
            plan_currency: res[0].default_currency.code,
          });
        }
      });
    }
  }, []);

  const mutation = useMutation(
    (post: CreatePlanRequestType) => Plan.createPlan(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to create Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const addFeatures = (newFeatures: FeatureType[]) => {
    for (let i = 0; i < newFeatures.length; i++) {
      if (
        planFeatures.some(
          (feat) => feat.feature_id === newFeatures[i].feature_id
        )
      ) {
      } else {
        setPlanFeatures((prev) => [...prev, newFeatures[i]]);
      }
    }
    setFeatureVisible(false);
  };

  const editFeatures = (feature_name: string) => {
    const currentFeature = planFeatures.filter(
      (item) => item.feature_name === feature_name
    )[0];
    setFeatureVisible(true);
  };

  const removeFeature = (feature_id: string) => {
    setPlanFeatures(
      planFeatures.filter((item) => item.feature_id !== feature_id)
    );
  };

  const onFinishFailed = () => {
    //
  };

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
  };

  const handleComponentAdd = (newData: any) => {
    const old = componentsData;

    /// check if the metricId on newdata is already in a component in componentsData
    // if it is then raise an alert with toast
    // if not then add the new data to the componentsData

    const metricComponentExists = componentsData.some(
      (item) => item.metric_id === newData.metric_id
    );

    if (metricComponentExists && !editComponentItem) {
      toast.error("Metric already exists in another component", {
        position: toast.POSITION.TOP_CENTER,
      });
      return;
    }

    if (editComponentItem) {
      const index = componentsData.findIndex(
        (item) => item.metric_id === editComponentItem.metric_id
      );
      old[index] = newData;
      setComponentsData(old);
    } else {
      const newComponentsData = [
        ...old,
        {
          ...newData,
          id: Math.floor(Math.random() * 1000),
        },
      ];
      setComponentsData(newComponentsData);
    }

    setEditComponentsItem(undefined);
    setcomponentVisible(false);
  };

  const handleComponentEdit = (id: string) => {
    const currentComponent = componentsData.filter(
      (item) => item.metric_id === id
    )[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (metric_id: string) => {
    setComponentsData(
      componentsData.filter((item) => item.metric_id !== metric_id)
    );
  };

  const hideFeatureModal = () => {
    setFeatureVisible(false);
  };

  const showFeatureModal = () => {
    setFeatureVisible(true);
  };

  const goBackPage = () => {
    navigate(-1);
  };

  const setExternalLinks = (links: string[]) => {
    form.setFieldValue("initial_external_links", links);
  };

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then(() => {
        const values = form.getFieldsValue(true);
        const usagecomponentslist: CreateComponentRequestType[] = [];
        const components: any = Object.values(componentsData);

        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponentRequestType = {
              metric_id: components[i].metric_id,
              tiers: components[i].tiers,
              reset_interval_count: components[i].reset_interval_count,
              reset_interval_unit: components[i].reset_interval_unit,
              invoicing_interval_count: components[i].invoicing_interval_count,
              invoicing_interval_unit: components[i].invoicing_interval_unit,
              prepaid_charge: components[i].prepaid_charge,
            };

            usagecomponentslist.push(usagecomponent);
          }
        }

        const featureIdList: string[] = [];

        const features: any = Object.values(planFeatures);

        if (features) {
          for (let i = 0; i < features.length; i++) {
            featureIdList.push(features[i].feature_id);
          }
        }

        const recurring_charges: CreateRecurringCharge[] = recurringCharges.map(
          (recurringCharge) => ({
            amount: recurringCharge.amount,
            charge_behavior: recurringCharge.charge_behavior,
            charge_timing: recurringCharge.charge_timing,
            name: recurringCharge.name,
          })
        );

        if (values.usage_billing_frequency === "yearly") {
          values.usage_billing_frequency = "end_of_period";
        }

        const initialPlanVersion: CreatePlanRequestType["initial_version"] = {
          version: 1,
          localized_name: values.localized_name,
          recurring_charges,
          // @ts-expect-error TODO: fix this
          transition_to_plan_id: values.transition_to_plan_id,
          components: usagecomponentslist,
          features: featureIdList,
          usage_billing_frequency: values.usage_billing_frequency,
          currency_code: selectedCurrency!.code,
          plan_name: values.name,
        };

        if (
          values.price_adjustment_type !== undefined &&
          values.price_adjustment_type !== "none"
        ) {
          if (
            values.price_adjustment_type === "percentage" ||
            values.price_adjustment_type === "fixed"
          ) {
            values.price_adjustment_amount =
              Math.abs(values.price_adjustment_amount) * -1;
          }

          initialPlanVersion.price_adjustment = {
            price_adjustment_type: values.price_adjustment_type,
            price_adjustment_amount: values.price_adjustment_amount,
          };
        }

        if (values.align_plan === "calendar_aligned") {
          if (
            values.plan_duration === "yearly" ||
            values.plan_duration === "quarterly"
          ) {
            initialPlanVersion.day_anchor = values.day_of_month;
            initialPlanVersion.month_anchor = month;
          }
          if (values.plan_duration === "monthly") {
            initialPlanVersion.day_anchor = values.day_of_month;
          }
        }

        const plan: CreatePlanRequestType = {
          plan_name: values.name,
          plan_duration: values.plan_duration,
          initial_version: initialPlanVersion,
        };

        const links = values.initial_external_links;

        if (links?.length) {
          plan.initial_external_links = links.map((link) => ({
            source: "stripe",
            external_plan_id: link,
          }));
        }

        mutation.mutate(plan);
      })
      .catch((info) => {});
  };

  const STEPS = [
    {
      title: "Plan Information",
      slug: "plan-information",
      Component: PlanInformation,
      validate: validatePlanInformation,
    },
    {
      title: "Version Information",
      slug: "version-information",
      Component: VersionInformation,
      validate: validateVersionInformation,
    },
    {
      title: "Charges & Features",
      slug: "setup-charges-and-features",
      Component: ChargesAndFeatures,
      validate: validateChargesAndFeatures,
    },
  ];

  const step = STEPS[currentStep];

  return (
    <PageLayout title="Create a plan" onBack={goBackPage}>
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{
            flat_rate: 0,
            flat_fee_billing_type: "in_advance",
            price_adjustment_type: "none",
            plan_duration: "monthly",
            align_plan: "calendar_aligned",
            usage_billing_frequency: "monthly",
            localized_name: null,
          }}
          onChange={async () => {
            const isValid = await step.validate(form);
            setIsCurrentStepValid(isValid);
          }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          layout="vertical"
          labelAlign="left"
        >
          <Row gutter={[24, 24]} justify="space-between">
            <Col span={24}>
              <div
                className={clsx(["flex items-center justify-between", "mb-6"])}
              >
                <BreadCrumbs
                  items={STEPS.map((step) => step.title)}
                  activeItem={currentStep}
                  onItemClick={async (idx) => {
                    if (idx > currentStep) {
                      const isValid = await step.validate(form);
                      if (!isValid) {
                        return;
                      }
                    }

                    setCurrentStep(idx);
                  }}
                />
                <Button
                  type="primary"
                  disabled={!isCurrentStepValid}
                  style={{
                    background: "#C3986B",
                    color: "#FFFFFF",
                    borderColor: "#C3986B",
                    opacity: !isCurrentStepValid ? 0.5 : 1,
                  }}
                  onClick={async () => {
                    if (currentStep < STEPS.length - 1) {
                      setIsCurrentStepValid(false);
                      setCurrentStep(currentStep + 1);
                      return;
                    }

                    form.submit();
                  }}
                >
                  {currentStep === STEPS.length - 1 ? "Publish" : "Next step"}
                </Button>
              </div>
            </Col>
          </Row>

          <step.Component
            form={form}
            allPlans={allPlans}
            setAllPlans={setAllPlans}
            availableBillingTypes={availableBillingTypes}
            setAvailableBillingTypes={setAvailableBillingTypes}
            month={month}
            setMonth={setMonth}
            allCurrencies={allCurrencies}
            setAllCurrencies={setAllCurrencies}
            selectedCurrency={selectedCurrency}
            setSelectedCurrency={setSelectedCurrency}
            priceAdjustmentType={priceAdjustmentType}
            setPriceAdjustmentType={setPriceAdjustmentType}
            setExternalLinks={setExternalLinks}
            planFeatures={planFeatures}
            editFeatures={editFeatures}
            removeFeature={removeFeature}
            showFeatureModal={showFeatureModal}
            componentsData={componentsData}
            handleComponentEdit={handleComponentEdit}
            deleteComponent={deleteComponent}
            showComponentModal={showComponentModal}
            setIsCurrentStepValid={setIsCurrentStepValid}
            showRecurringChargeModal={showRecurringChargeModal}
            setShowRecurringChargeModal={setShowRecurringChargeModal}
            recurringCharges={recurringCharges}
            setRecurringCharges={setRecurringCharges}
          />
        </Form>

        {componentVisible && (
          <UsageComponentForm
            visible={componentVisible}
            onCancel={hideComponentModal}
            componentsData={componentsData}
            handleComponentAdd={handleComponentAdd}
            editComponentItem={editComponentItem}
            setEditComponentsItem={setEditComponentsItem}
            currency={selectedCurrency!}
            planDuration={form.getFieldValue("plan_duration")}
          />
        )}
        {featureVisible && (
          <FeatureForm
            visible={featureVisible}
            onCancel={hideFeatureModal}
            onAddFeatures={addFeatures}
          />
        )}

        {showRecurringChargeModal ? (
          <RecurringChargeForm
            visible={showRecurringChargeModal}
            selectedCurrency={selectedCurrency}
            onCancel={() => setShowRecurringChargeModal(false)}
            onAddRecurringCharges={(newRecurringCharge) => {
              setRecurringCharges((prev) => [...prev, newRecurringCharge]);
              setShowRecurringChargeModal(false);
            }}
          />
        ) : null}
      </Form.Provider>
    </PageLayout>
  );
}

export default CreatePlan;
