/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable no-shadow */
/* eslint-disable camelcase */
/* eslint-disable no-plusplus */
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
} from "antd";
// @ts-ignore
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import moment from "moment";

import {
  CreateComponent,
  CreateInitialVersionType,
  CreatePlanType,
  PlanType,
} from "../types/plan-type";
import SelectComponent from "../components/base/Select/Select";
import { Plan, Organization } from "../api/api";
import { CreateFeatureType, FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import LinkExternalIds from "../components/Plans/LinkExternalIds";
import { PageLayout } from "../components/base/PageLayout";
import { ComponentDisplay } from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";
import { CurrencyType } from "../types/pricing-unit-type";
import { CreateRecurringCharge } from "../types/plan-type";
import { PlusOutlined } from "@ant-design/icons";
import capitalize from "../helpers/capitalize";
import RecurringChargesForm from "../components/Plans/PlanCreate/RecurringChargesForm";
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
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [allCurrencies, setAllCurrencies] = useState<CurrencyType[]>([]);
  const [selectedCurrency, setSelectedCurrency] = useState<CurrencyType>({
    symbol: "",
    code: "",
    name: "",
  });
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [discountVisible, setDiscountVisible] = useState(false);
  const [recurringChargesVisible, setRecurringChargesVisible] = useState(false);
  const [priceAdjustmentType, setPriceAdjustmentType] =
    useState<string>("none");
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<CreateComponent[]>([]);
  const [form] = Form.useForm();
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);
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

  const months = moment.months();
  const mutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
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

  const setExternalLinks = (links: string[]) => {
    form.setFieldValue("initial_external_links", links);
  };

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
        const recurring_charges: CreateRecurringCharge[] = [];
        recurring_charges.push({
          amount: values.flat_rate,
          charge_behavior: "prorate",
          charge_timing: values.flat_fee_billing_type,
          name: "Flat Fee",
        });

        if (values.usage_billing_frequency === "yearly") {
          values.usage_billing_frequency = "end_of_period";
        }
        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          recurring_charges: recurring_charges,
          transition_to_plan_id: values.transition_to_plan_id,
          components: usagecomponentslist,
          features: featureIdList,
          usage_billing_frequency: values.usage_billing_frequency,
          currency_code: values.plan_currency,
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
        const plan: CreatePlanType = {
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

  return (
    <PageLayout
      title="Create Plan"
      onBack={goBackPage}
      extra={[
        <Button
          key="create"
          onClick={() => form.submit()}
          size="large"
          type="primary"
        >
          Create new plan
        </Button>,
      ]}
    >
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
          }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={[24, 24]}>
            <Col span={10}>
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card
                    className="!bg-card !font-alliance"
                    title="Plan Information"
                  >
                    <Form.Item
                      name="name"
                      rules={[
                        {
                          required: true,
                          message: "Please Name Your Plan",
                        },
                      ]}
                    >
                      <label className="font-alliance mb-4 required">
                        Plan Name
                      </label>
                      <Input
                        className="w-full"
                        placeholder="Ex: Starter Plan"
                      />
                    </Form.Item>
                    <Form.Item name="description">
                      <label className="font-alliance mb-4 required">
                        Description
                      </label>
                      <Input
                        className="w-full"
                        type="textarea"
                        placeholder="Ex: Cheapest plan for small scale businesses"
                      />
                    </Form.Item>
                    <Form.Item
                      label="Plan Duration"
                      name="plan_duration"
                      rules={[
                        {
                          required: true,
                          message: "Please select a duration",
                        },
                      ]}
                    >
                      <Radio.Group
                        onChange={(e) => {
                          if (e.target.value === "monthly") {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "monthly"
                            );
                          } else if (e.target.value === "quarterly") {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "quarterly"
                            );
                          } else {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                              { label: "Yearly", name: "yearly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "yearly"
                            );
                          }
                        }}
                      >
                        <Radio value="monthly">Monthly</Radio>
                        <Radio value="quarterly">Quarterly</Radio>
                        <Radio value="yearly">Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>
                    <Form.Item
                      label="When To Invoice"
                      name="align_plan"
                      rules={[
                        {
                          required: true,
                          message: "Please Select One",
                        },
                      ]}
                    >
                      <Radio.Group>
                        <Radio value="calendar_aligned">
                          Every{" "}
                          <Form.Item name="day_of_month" noStyle>
                            <InputNumber
                              min={1}
                              max={31}
                              size="small"
                              style={{ width: "50px" }}
                              placeholder="Day"
                            />
                          </Form.Item>{" "}
                          {["quarterly", "yearly"].includes(
                            form.getFieldValue("plan_duration")
                          ) && (
                            <>
                              of{" "}
                              <Form.Item name="month_of_year" noStyle>
                                <select
                                  className="border border-black rounded-sm outline-none"
                                  onChange={(e) =>
                                    setMonth(Number(e.target.value))
                                  }
                                  name="month_of_year"
                                  id="month_of_year"
                                >
                                  {months.map((month, i) => (
                                    <option value={i + 1} key={month}>
                                      {month}
                                    </option>
                                  ))}
                                </select>
                              </Form.Item>
                            </>
                          )}
                          {["monthly"].includes(
                            form.getFieldValue("plan_duration")
                          ) && "of the Month"}
                        </Radio>
                        <Radio value="subscription_aligned">
                          Start of Subscription
                        </Radio>
                      </Radio.Group>
                    </Form.Item>

                    <div className="flex gap-56">
                      <Form.Item
                        rules={[
                          {
                            required: true,
                            message: "Please Add A Billing Type",
                          },
                        ]}
                        name="flat_fee_billing_type"
                      >
                        <label className="font-alliance  required whitespace-nowrap">
                          Recurring Billing Type
                        </label>
                        <Select className="!mt-4 !w-[170%]">
                          <Select.Option value="in_advance">
                            Pay in advance
                          </Select.Option>
                          <Select.Option value="in_arrears">
                            Pay in arrears
                          </Select.Option>
                        </Select>
                      </Form.Item>
                      <Form.Item
                        name="transition_to_plan_id"
                        rules={[
                          {
                            required: true,
                            message: "Please Add a Next Plan",
                          },
                        ]}
                      >
                        <label className="font-alliance whitespace-nowrap mb-4 required">
                          Plan On Next Cycle
                        </label>
                        <Select className="mt-4 w-full">
                          {allPlans.map((plan) => (
                            <Select.Option
                              key={plan.plan_id}
                              value={plan.plan_id}
                            >
                              {plan.plan_name}
                            </Select.Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </div>
                    <div className="flex">
                      <Form.Item
                        name="flat_rate"
                        rules={[
                          {
                            required: true,
                            message: "Please Add a Base Cost",
                          },
                        ]}
                      >
                        <label className="font-alliance whitespace-nowrap mb-4 required">
                          {" "}
                          Base Cost
                        </label>
                        <InputNumber
                          className="mt-4"
                          controls={false}
                          addonBefore={
                            selectedCurrency ? selectedCurrency.symbol : "-"
                          }
                          defaultValue={0}
                          precision={2}
                        />
                      </Form.Item>
                      <Form.Item name="plan_currency">
                        <label className="mb-4 required whitespace-nowrap">
                          Plan Currency
                        </label>
                        <Select
                          className="mt-4 w-full"
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
                            <Select.Option
                              key={currency.code}
                              value={currency.code}
                            >
                              {currency.name} {currency.symbol}
                            </Select.Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </div>
                    <Form.Item
                      name="initial_external_links"
                      label="Link External IDs"
                    >
                      <LinkExternalIds
                        externalIds={[]}
                        setExternalLinks={setExternalLinks}
                      />
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>

            <Col span={14}>
              <Card
                title="Added Components"
                className=" !bg-card !font-alliance"
                extra={[
                  <Button
                    key="add-component"
                    htmlType="button"
                    className="!bg-transparent !border-none !text-gold"
                    onClick={() => showComponentModal()}
                  >
                    <PlusOutlined />
                    Add
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
                  <div className="mt-4">
                    <SelectComponent>
                      <SelectComponent.Label className="">
                        Billing Frequency
                      </SelectComponent.Label>
                      <SelectComponent.Select
                        disabled
                        className="!w-1/4"
                        onChange={() => {
                          //
                        }}
                      >
                        <SelectComponent.Option selected>
                          {form.getFieldValue("plan_duration")
                            ? capitalize(form.getFieldValue("plan_duration"))
                            : form.getFieldValue("plan_duration")}
                        </SelectComponent.Option>
                      </SelectComponent.Select>
                    </SelectComponent>
                  </div>
                </Form.Item>
              </Card>
              <Card
                className="w-full !mt-6 !bg-card !font-alliance"
                title="Added Features"
                extra={[
                  <Button
                    key="add-feature"
                    htmlType="button"
                    className="!bg-transparent !border-none !text-gold"
                    onClick={showFeatureModal}
                  >
                    <PlusOutlined />
                    Add
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

              <Card
                className="w-full !bg-card font-alliance !mt-6"
                title="Discount"
                extra={[
                  <Button
                    key="add-discount"
                    htmlType="button"
                    className="!bg-transparent !border-none !text-gold"
                    onClick={() => setDiscountVisible(!discountVisible)}
                  >
                    {!discountVisible ? (
                      <>
                        {" "}
                        <PlusOutlined />
                        Add
                      </>
                    ) : (
                      <div>Hide</div>
                    )}
                  </Button>,
                ]}
              >
                {discountVisible ? (
                  <div className="grid grid-cols-2">
                    <Form.Item
                      wrapperCol={{ span: 20 }}
                      label="Type"
                      name="price_adjustment_type"
                    >
                      <Select
                        onChange={(value) => {
                          setPriceAdjustmentType(value);
                        }}
                      >
                        <Select.Option value="none">None</Select.Option>
                        {/* <Select.Option value="price_override">
                        Overwrite Price
                      </Select.Option> */}
                        <Select.Option value="percentage">
                          Percentage Off
                        </Select.Option>
                        <Select.Option value="fixed">
                          Flat Discount
                        </Select.Option>
                      </Select>
                    </Form.Item>

                    {priceAdjustmentType !== "none" && (
                      <Form.Item
                        name="price_adjustment_amount"
                        wrapperCol={{ span: 24, offset: 4 }}
                        shouldUpdate={(prevValues, curValues) =>
                          prevValues.price_adjustment_type !==
                          curValues.price_adjustment_type
                        }
                        rules={[
                          {
                            required:
                              priceAdjustmentType !== undefined ||
                              priceAdjustmentType !== "none",
                            message: "Please enter a price adjustment value",
                          },
                        ]}
                      >
                        <InputNumber
                          addonAfter={
                            priceAdjustmentType === "percentage" ? "%" : null
                          }
                          addonBefore={
                            (priceAdjustmentType === "fixed" ||
                              priceAdjustmentType === "price_override") &&
                            selectedCurrency
                              ? selectedCurrency.symbol
                              : null
                          }
                        />
                      </Form.Item>
                    )}
                  </div>
                ) : (
                  <div className="Inter text-card-grey text-base">
                    No discount added yet
                  </div>
                )}
              </Card>
              <Card
                className="w-full !bg-card font-alliance !mt-6"
                title="Recurring Charges"
                extra={[
                  <Button
                    key="add-discount"
                    htmlType="button"
                    className="!bg-transparent !border-none !text-gold"
                    onClick={() =>
                      setRecurringChargesVisible(!recurringChargesVisible)
                    }
                  >
                    <PlusOutlined />
                    Add
                  </Button>,
                ]}
              >
                {recurringChargesVisible ? (
                  <div className="grid grid-cols-2">for nw</div>
                ) : (
                  <div className="Inter text-card-grey text-base">
                    No added recurring charges yet
                  </div>
                )}
              </Card>
            </Col>
          </Row>
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
        {recurringChargesVisible && (
          <RecurringChargesForm
            visible={recurringChargesVisible}
            onClose={() => setRecurringChargesVisible(false)}
            preferredCurrency={selectedCurrency.symbol}
            submitHandler={() => {
              //
            }}
          />
        )}
      </Form.Provider>
    </PageLayout>
  );
}

export default CreatePlan;
