// @ts-ignore
import React, { FC, useState } from "react";
import { useMutation, useQuery, UseQueryResult } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Form, Input, Button, Modal, Select } from "antd";
import { Organization, PricingUnits } from "../../../../api/api";
import { EditOutlined } from "@ant-design/icons";
import { PricingUnit } from "../../../../types/pricing-unit-type";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../LoadingSpinner";
import PricingUnitDropDown from "../../../PricingUnitDropDown";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const GeneralTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [isEdit, setIsEdit] = useState(false);
  const [form] = Form.useForm();

  const {
    data: pricingUnits,
    isLoading: pricingUnitsLoading,
  }: UseQueryResult<PricingUnit[]> = useQuery<PricingUnit[]>(
    ["pricing_unit_list"],
    () =>
      PricingUnits.list().then((res) => {
        return res;
      })
  );

  const getCurrencies = () => {
    const items = data || [];
    if (false) {
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

  const { data, isLoading, isError } = useQuery(["organization"], () =>
    Organization.get().then((res) => {
      console.log(res);
      return res[0];
    })
  );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
        toast.success("Invite sent");
      },
      onError: (error: any) => {
        if (error.response.data) {
          toast.error(
            Array.isArray(error.response.data.email)
              ? error.response.data.email[0]
              : error.response.data.email
          );
        } else {
          toast.error("Cannot send an invite now, try again later.");
        }
      },
    }
  );

  const updateOrg = useMutation(
    (obj: { org_id: string; default_currency_code: string }) =>
      Organization.updateOrganization(obj.org_id, obj.default_currency_code),
    {
      onSuccess: () => {
        toast.success("Successfully Updated Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to Update Default Currency", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const handleSendInviteEmail = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };

  return (
    <div>
      <Typography.Title level={2}>Organization Settings</Typography.Title>

      <Divider />

      <div className="flex flex-col w-6/12 justify-between">
        {mutation.isLoading && <LoadingSpinner />}
        <p className=" text-[16px]">
          <b>Company Name:</b> {data?.company_name ? data.company_name : "N/A"}
        </p>
        <p className=" text-[16px]">
          <b className="">Default Organization Currency:</b>{" "}
          {data?.default_currency?.name} ({data?.default_currency?.symbol})
        </p>

        <div className="">
          <Button onClick={() => setIsEdit(true)} className="justify-self-end">
            Edit
          </Button>
        </div>
      </div>
      <Modal
        title="Edit Organization Settings"
        visible={isEdit}
        onCancel={() => setIsEdit(false)}
        okText="Save"
        onOk={() => {
          if (data) {
            updateOrg.mutate({
              org_id: data.organization_id,
              default_currency_code: form.getFieldValue(
                "default_currency_code"
              ),
            });
          }
          setIsEdit(false);
        }}
      >
        <div className="flex flex-col w-6/12 justify-between">
          <Form
            form={form}
            initialValues={{
              company_name: data?.company_name,
            }}
          >
            <Form.Item
              label="Company Name"
              name="company_name"
              rules={[
                {
                  required: true,
                },
              ]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              label="Default Organization Currency"
              name="default_currency"
            >
              <Select
                size="small"
                // onChange={setCurrentCurrency}
                options={getCurrencies()?.map((pc) => {
                  return { label: `${pc.name} ${pc.symbol}`, value: pc.code };
                })}
              />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  );
};

export default GeneralTab;
