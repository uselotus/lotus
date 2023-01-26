import { Button, Card, Form, Input, InputNumber, Select } from "antd";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";

import { CreateComponent, PlanType } from "../types/plan-type";
import { Plan, Organization, Addon } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { PageLayout } from "../components/base/PageLayout";
import { ComponentDisplay } from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";
import { CurrencyType } from "../types/pricing-unit-type";
import { AddonTypeOption, CreateAddonType } from "../types/addon-type";

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

const CreateAddOns = () => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [allCurrencies, setAllCurrencies] = useState<CurrencyType[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState<CurrencyType>({
    symbol: "",
    code: "",
    name: "",
  });
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [showInvoicing, setShowInvoicing] = useState(false);
  const [priceAdjustmentType, setPriceAdjustmentType] =
    useState<string>("none");
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<CreateComponent[]>([]);
  const [form] = Form.useForm();
  const [addon_name, setAddonName] = useState<string | null>(null!);
  const [description, setDescription] = useState<string | null>(null);
  const [billing_frequency, setBillingFrequency] = useState<string | null>(
    null
  );
  const [addon_type, setAddonType] = useState<AddonTypeOption>("flat_fee");
  const [base_cost, setBaseCost] = useState<number | null>(0.0);
  const [recurring_flat_fee_timing, setRecurringFlatFeeTiming] = useState("");
  const [invoice_when, setInvoiceWhen] = useState<string | null>(null);
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);
  const [editComponentItem, setEditComponentsItem] =
    useState<CreateComponent>();
  let card: React.ReactNode | null = null;
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
    (add_on: CreateAddonType) => Addon.createAddon(add_on),
    {
      onSuccess: () => {
        toast.success("Successfully created Add-on", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["add-ons"]);
        navigate("/add-ons");
      },
      onError: () => {
        toast.error("Failed to create Add-on", {
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

  const onFinishFailed = (errorInfo: any) => {};

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
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

  const handleComponentEdit = (id: any) => {
    const currentComponent = componentsData.filter((item) => item.id === id)[0];

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

  const submitAddons = () => {
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
    const addons = {
      addon_name,
      description,
      addon_type,
      billing_frequency,
      flat_rate: base_cost!,
      components: usagecomponentslist.length ? usagecomponentslist : [],
      features: featureIdList.length ? featureIdList : [],
      invoice_when,
      recurring_flat_fee_timing: recurring_flat_fee_timing
        ? recurring_flat_fee_timing
        : null,
      currency_code: selectedCurrency.code,
    };
    mutation.mutate(addons);
  };
  if (
    (addon_type === "usage" && billing_frequency === "one_time") ||
    (addon_type === "flat_fee" && billing_frequency === "recurring")
  ) {
    console.log("yasdh");
    card = (
      <Card
        title="Added Components"
        className="h-full mb-6"
        style={{
          borderRadius: "0.5rem",
          borderWidth: "2px",
          borderColor: "#EAEAEB",
          borderStyle: "solid",
        }}
        extra={[
          <Button
            key="add-component"
            htmlType="button"
            onClick={() => showComponentModal()}
          >
            Add Component
          </Button>,
        ]}
      >
        <Form.Item
          wrapperCol={{ span: 24 }}
          shouldUpdate={(prevValues, curValues) =>
            prevValues.components !== curValues.components
          }
        >
          <ComponentDisplay
            componentsData={componentsData}
            handleComponentEdit={handleComponentEdit}
            deleteComponent={deleteComponent}
            pricing_unit={selectedCurrency}
          />
        </Form.Item>
      </Card>
    );
  }
  return (
    <PageLayout
      title="Create Add Ons"
      onBack={goBackPage}
      extra={[
        <Button
          key="create"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
          onClick={() => form.submit()}
          size="large"
          type="primary"
        >
          Preview & publish
        </Button>,
      ]}
      hasBackButton
      aboveTitle
      backButton={
        <div className="mt-10">
          <Button
            onClick={() => navigate(-1)}
            type="primary"
            size="large"
            className="ml-[10px] mt-[32px]"
            key="create-custom-plan"
            style={{
              background: "#F5F5F5",
              borderColor: "#F5F5F5",
            }}
          >
            <div className="flex items-center justify-between text-black">
              <div>&larr; Go back</div>
            </div>
          </Button>
        </div>
      }
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_addons"
          onFinish={submitAddons}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <div className="grid gap-12 grid-cols-1  md:grid-cols-3">
            <Card
              style={{
                borderRadius: "0.5rem",
                borderWidth: "2px",
                borderColor: "#EAEAEB",
                borderStyle: "solid",
              }}
              className="col-span-1"
              title="Add-on Information"
            >
              <Form.Item name="add-on name">
                <label className="mb-4 required">Add-on Name </label>
                <Input
                  className="w-full"
                  placeholder="Ex: words count"
                  onChange={(e) => setAddonName(e.target.value)}
                />
              </Form.Item>
              <Form.Item name="description">
                <label className="mb-4 required">Description </label>
                <Input
                  className="w-full"
                  type="textarea"
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Ex: Cheapest add-on for small scale businesses"
                />
              </Form.Item>
              <Form.Item name="addon_type">
                <label className="mb-4 required">Type</label>
                <Select
                  placeholder="Flat"
                  onChange={(e) => {
                    if (e === "flat_fee") {
                      setShowInvoicing(true);
                    } else {
                      setShowInvoicing(false);
                    }
                    setAddonType(e);
                  }}
                  className="w-full"
                >
                  <Select.Option value="flat_fee">Flat</Select.Option>
                  <Select.Option value="usage">Usage Based</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item name="billing frequency">
                <label className="mb-4 required">Billing Frequency</label>
                <Select
                  onChange={(e) => setBillingFrequency(e)}
                  className="w-full"
                  placeholder="One-Time"
                >
                  <Select.Option value="one_time">One-Time</Select.Option>
                  <Select.Option value="recurring">Recurring</Select.Option>
                </Select>
              </Form.Item>
              <div className="grid grid-cols-2 gap-6 mt-2 mb-2">
                <Form.Item name="base cost">
                  <label className="mb-4 required">Base Cost</label>
                  <InputNumber
                    className="w-full"
                    type="number"
                    onChange={(e) => {
                      setBaseCost(e!);
                    }}
                    defaultValue={0}
                    precision={2}
                    controls={false}
                  />
                </Form.Item>
                <Form.Item name="currency_code">
                  <label className="mb-4">Currency</label>
                  <Select
                    className="w-full"
                    onChange={(value) => {
                      const selectedCurrency = allCurrencies.find(
                        (currency) => currency.code === value
                      );
                      if (selectedCurrency) {
                        setSelectedCurrency(selectedCurrency);
                      }
                    }}
                    value={selectedCurrency?.symbol}
                  >
                    {allCurrencies.map((currency) => (
                      <Select.Option key={currency.code} value={currency.code}>
                        {currency.name} {currency.symbol}
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              </div>

              {billing_frequency === "recurring" && (
                <Form.Item name="recurring_flat_fee_timing">
                  <label className="mb-4 nowrap required"> Billing Type</label>
                  <Select
                    onChange={(e) => setRecurringFlatFeeTiming(e)}
                    className="w-full"
                    placeholder="Pay in advance"
                  >
                    <Select.Option value="in_advance">
                      Pay in advance
                    </Select.Option>
                    <Select.Option value="in_arrears">
                      Pay in arrears
                    </Select.Option>
                  </Select>
                </Form.Item>
              )}

              {showInvoicing && (
                <Form.Item name="invoice_when">
                  <label className="mb-4">Invoicing When</label>
                  <Select
                    onChange={(e) => setInvoiceWhen(e)}
                    placeholder="On Attach"
                    className="w-full"
                  >
                    <Select.Option value="invoice_on_attach">
                      On Attach
                    </Select.Option>
                    <Select.Option value="invoice_on_subscription_end">
                      On Subscription End
                    </Select.Option>
                  </Select>
                </Form.Item>
              )}
            </Card>

            <div className="col-span-2">
              {card}

              <Card
                className="w-full"
                title="Added Features"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
                extra={[
                  <Button
                    key="add-feature"
                    htmlType="button"
                    onClick={showFeatureModal}
                  >
                    Add Feature
                  </Button>,
                ]}
              >
                <Form.Item
                  wrapperCol={{ span: 24 }}
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  <FeatureDisplay
                    planFeatures={planFeatures}
                    removeFeature={removeFeature}
                    editFeatures={editFeatures}
                  />
                </Form.Item>
              </Card>
            </div>
          </div>
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
          />
        )}
        {featureVisible && (
          <FeatureForm
            visible={featureVisible}
            onCancel={hideFeatureModal}
            onAddFeatures={addFeatures}
          />
        )}
      </Form.Provider>
    </PageLayout>
  );
};

export default CreateAddOns;
