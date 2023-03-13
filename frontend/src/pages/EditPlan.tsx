import {
  Button,
  Select,
  Form,
  Card,
  Input,
  InputNumber,
  Row,
  Col,
  Radio,
} from "antd";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { noop } from "lodash";
import UsageComponentForm from "../components/Plans/UsageComponentForm";

import {
  CreatePlanType,
  CreateComponent,
  PlanType,
  PlanDetailType,
  CreateInitialVersionType,
  CreatePlanVersionType,
} from "../types/plan-type";
import { Organization, Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { usePlanUpdater } from "../context/PlanContext";
import { PageLayout } from "../components/base/PageLayout";
import TargetCustomerForm from "../components/Plans/TargetCustomerForm";
import VersionActiveForm from "../components/Plans/VersionActiveForm";
import { CurrencyType } from "../types/pricing-unit-type";
import { components } from "../gen-types";
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

interface CustomizedState {
  plan: PlanType;
}
const durationConversion = {
  monthly: "Month",
  quarterly: "Quarter",
  yearly: "Year",
};

interface Props {
  type: "backtest" | "version" | "custom";
  plan: PlanDetailType;
  versionIndex: number;
}

function EditPlan({ type, plan, versionIndex }: Props) {
  const [showRecurringChargeModal, setShowRecurringChargeModal] =
    useState<boolean>(false);
  const [isCurrentStepValid, setIsCurrentStepValid] = useState<boolean>(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [targetCustomerFormVisible, setTargetCustomerFormVisible] =
    useState<boolean>(false);
  const [versionActiveFormVisible, setVersionActiveFormVisible] =
    useState<boolean>(false);
  const [activeVersion, setActiveVersion] = useState<boolean>(false);
  const [activeVersionType, setActiveVersionType] = useState<string>();
  const [month, setMonth] = useState(1);
  const [allCurrencies, setAllCurrencies] = useState<CurrencyType[]>([]);
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<any>([]);
  const [form] = Form.useForm();
  const { setReplacementPlan } = usePlanUpdater();
  const [editComponentItem, setEditComponentsItem] = useState<any>();
  const [targetCustomerId, setTargetCustomerId] = useState<string>(); // target customer id
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [availableBillingTypes, setAvailableBillingTypes] = useState<
    { name: string; label: string }[]
  >([
    { label: "Monthly", name: "monthly" },
    { label: "Quarterly", name: "quarterly" },
    { label: "Yearly", name: "yearly" },
  ]);
  const [priceAdjustmentType, setPriceAdjustmentType] = useState<string>(
    plan.versions[versionIndex].price_adjustment?.price_adjustment_type ??
      "none"
  );
  const [selectedCurrency, setSelectedCurrency] = useState<CurrencyType>(
    plan.versions[versionIndex].currency ?? {
      symbol: "",
      code: "",
      name: "",
    }
  );
  const [recurringCharges, setRecurringCharges] = useState<
    components["schemas"]["PlanDetail"]["versions"][0]["recurring_charges"]
  >([]);

  const queryClient = useQueryClient();

  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>(
    plan.versions[versionIndex].features
  );

  useEffect(() => {
    if (!allPlans?.length) {
      Plan.getPlans().then((data) => setAllPlans(data));
    }
  }, []);

  useEffect(() => {
    const initialComponents: any[] = plan.versions[versionIndex].components.map(
      (component) => ({
        metric: component.billable_metric.metric_name,
        tiers: component.tiers,
        id: component.billable_metric.metric_id,
        metric_id: component.billable_metric.metric_id,
        pricing_unit: component.pricing_unit,
      })
    );
    setComponentsData(initialComponents);
  }, [plan.versions, versionIndex]);

  useEffect(() => {
    if (!allCurrencies?.length) {
      Organization.get().then((res) => {
        setAllCurrencies(res[0].available_currencies);
        form.setFieldsValue({
          plan_currency: selectedCurrency.code,
        });
      });
    }
  }, []);

  const mutation = useMutation(
    (data: CreatePlanVersionType) => Plan.createVersion(data),
    {
      onSuccess: () => {
        toast.success("Successfully created new version", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries(["plan_list"]);
        navigate(`/plans/${plan.plan_id}`);
      },
      onError: () => {
        toast.error("Failed to create version", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const createPlanMutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: (res) => {
        queryClient.invalidateQueries(["plan_list"]);
        form.resetFields();
        if (type == "backtest") {
          setReplacementPlan(res);
          navigate("/create-experiment");
        }
        if (type == "custom") {
          navigate("/plans");
        }
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
          (feat) => feat.feature_name === newFeatures[i].feature_name
        )
      ) {
      } else {
        setPlanFeatures((prev) => [...prev, newFeatures[i]]);
      }
    }
    setFeatureVisible(false);
  };

  const editFeatures = (featureName: string) => {
    const currentFeature = planFeatures.filter(
      (item) => item.feature_name === featureName
    )[0];
    setFeatureVisible(true);
  };

  const removeFeature = (featureName: string) => {
    setPlanFeatures(
      planFeatures.filter((item) => item.feature_name !== featureName)
    );
  };

  const onFinishFailed = (errorInfo: any) => {};

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
  };

  const hideTargetCustomerForm = () => {
    setTargetCustomerFormVisible(false);
  };

  const handleComponentAdd = (newData: any) => {
    const old = componentsData;
    if (editComponentItem) {
      const index = componentsData.findIndex(
        (item) => item.id === editComponentItem.id
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

  const handleComponentEdit = (name: string) => {
    const currentComponent = componentsData.filter(
      (item) => item.id === name
    )[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (id: string) => {
    setComponentsData(componentsData.filter((item) => item.id !== id));
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

  const onFinish = () => {
    form
      .validateFields()
      .then(() => {
        if (type === "custom") {
          setTargetCustomerFormVisible(true);
        } else if (type === "version") {
          setVersionActiveFormVisible(true);
        } else {
          form.submit();
        }
      })
      .catch((errorInfo) => {
        toast.error(errorInfo.errorFields[0].errors[0]);
      });
  };

  const completeCustomPlan = (customerId: string) => {
    setTargetCustomerId(customerId);
    form.submit();
  };

  const completeNewVersion = (active: boolean, activeType: string) => {
    setActiveVersion(active);
    if (active) {
      setActiveVersionType(activeType);
    }
    form.submit();
  };

  /// Submit Pricing Plan Http Request
  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components: any = Object.values(componentsData);
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              metric_id: components[i].metric_id,
              tiers: components[i].tiers,
              proration_granularity: components[i].proration_granularity,
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

        if (values.usage_billing_frequency === "yearly") {
          values.usage_billing_frequency = "end_of_period";
        }

        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          recurring_charges: recurringCharges,
          transition_to_plan_id: values.transition_to_plan_id,
          components: usagecomponentslist,
          features: featureIdList,
          usage_billing_frequency: values.usage_billing_frequency,
          currency_code: values.plan_currency.code,
        };
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

        const newPlan: CreatePlanType = {
          plan_name: values.name,
          plan_duration: values.plan_duration,
          initial_version: initialPlanVersion,
        };
        if (type === "backtest") {
          newPlan.status = "experimental";
          createPlanMutation.mutate(newPlan);
        } else if (type === "version") {
          const newVersion: CreatePlanVersionType = {
            plan_id: plan.plan_id,
            description: values.description,
            recurring_charges: recurringCharges,
            transition_to_plan_id: values.transition_to_plan_id,
            components: usagecomponentslist,
            features: featureIdList,
            usage_billing_frequency: values.usage_billing_frequency,
            make_active: activeVersion,
            make_active_type: activeVersionType,
            currency_code: values.plan_currency.code,
          };

          if (values.align_plan === "calendar_aligned") {
            if (values.plan_duration === "yearly") {
              newVersion.day_anchor = 1;
              newVersion.month_anchor = 1;
            }
            if (values.plan_duration === "monthly") {
              newVersion.day_anchor = 1;
            }
            if (values.plan_duration === "quarterly") {
              newVersion.day_anchor = 1;
              newVersion.month_anchor = 1;
            }
          }

          if (
            values.price_adjustment_type !== undefined &&
            values.price_adjustment_type !== "none"
          ) {
            newVersion.price_adjustment = {
              price_adjustment_type: values.price_adjustment_type,
              price_adjustment_amount: values.price_adjustment_amount,
            };
          }

          mutation.mutate(newVersion);
        } else if (type === "custom") {
          // target_id = await targetCustomerFormVisible(true);

          newPlan.parent_plan_id = plan.plan_id;
          newPlan.target_customer_id = targetCustomerId;
          createPlanMutation.mutate(newPlan);
        }
      })
      .catch(noop);
  };

  function returnPageTitle(): string {
    if (type === "backtest") {
      return "Backtest Plan";
    }
    if (type === "version") {
      return `Create New Version:` + ` ${plan.plan_name}`;
    }
    return `Create Custom Plan:` + ` ${plan.plan_name}`;
  }

  function returnSubmitButtonText(): string {
    if (type === "backtest") {
      return "Create new Plan";
    }
    if (type === "version") {
      return "Publish version";
    }
    return "Create custom plan";
  }

  const getDisabledFields = (formType: string): string[] => {
    if (formType === "version") {
      return ["name", "plan_duration", "initial_external_links"];
    }

    if (formType === "custom") {
      return ["name", "plan_duration", "initial_external_links"];
    }

    return [];
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
    <PageLayout title={returnPageTitle()}>
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{
            name: plan.plan_name,
            description: plan.versions[versionIndex].description,
            flat_rate: plan.versions[versionIndex].flat_rate,
            pay_in_advance: plan.versions[versionIndex].flat_fee_billing_type,
            usage_billing_frequency:
              plan.versions[versionIndex].usage_billing_frequency ||
              plan.plan_duration,
            plan_duration: plan.plan_duration,
            flat_fee_billing_type:
              plan.versions[versionIndex].flat_fee_billing_type,
            price_adjustment_amount:
              plan.versions[versionIndex].price_adjustment
                ?.price_adjustment_amount,
            price_adjustment_type:
              plan.versions[versionIndex].price_adjustment
                ?.price_adjustment_type || "none",
            align_plan:
              plan.versions[versionIndex].day_anchor !== undefined
                ? "calendar_aligned"
                : "subscription_aligned",
            plan_currency: selectedCurrency,
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
              <div className="flex items-center justify-between mb-6">
                <BreadCrumbs
                  items={STEPS.map(({ title }) => title)}
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
                <div className="inline-flex justify-end items-center gap-2">
                  <Button
                    key="back"
                    onClick={goBackPage}
                    icon={<ArrowLeftOutlined />}
                    type="default"
                  >
                    Back
                  </Button>
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

                      onFinish();
                    }}
                  >
                    {currentStep === STEPS.length - 1
                      ? returnSubmitButtonText()
                      : "Next step"}
                  </Button>
                </div>
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
            setExternalLinks={noop}
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
            disabledFields={getDisabledFields(type)}
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
            currency={selectedCurrency}
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

      {targetCustomerFormVisible ? (
        <TargetCustomerForm
          visible={targetCustomerFormVisible}
          onCancel={hideTargetCustomerForm}
          onAddTargetCustomer={completeCustomPlan}
        />
      ) : null}

      {versionActiveFormVisible ? (
        <VersionActiveForm
          visible={versionActiveFormVisible}
          onCancel={() => setVersionActiveFormVisible(false)}
          onOk={completeNewVersion}
        />
      ) : null}
    </PageLayout>
  );
}

export default EditPlan;
