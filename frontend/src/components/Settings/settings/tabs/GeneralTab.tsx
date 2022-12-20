// @ts-ignore
import React, { FC, useState } from "react";
import {
  useMutation,
  useQuery,
  UseQueryResult,
  useQueryClient,
} from "react-query";
import { useNavigate } from "react-router-dom";
import {
  Divider,
  Typography,
  Form,
  Input,
  Button,
  Modal,
  Select,
  Tag,
} from "antd";
import { Organization, PricingUnits } from "../../../../api/api";
import { EditOutlined } from "@ant-design/icons";
import { PricingUnit } from "../../../../types/pricing-unit-type";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../LoadingSpinner";
import PricingUnitDropDown from "../../../PricingUnitDropDown";
import useGlobalStore, {
  IOrgStoreType,
} from "../../../../stores/useGlobalstore";
import { QueryErrors } from "../../../../types/error-response-types";

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
  const queryClient = useQueryClient();
  const org = useGlobalStore((state) => state.org);
  const setOrgInfoToStore = useGlobalStore((state) => state.setOrgInfo);
  const [currentCurrency, setCurrentCurrency] = useState("");

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

  const { isLoading } = useQuery(
    ["organization"],
    () =>
      Organization.get().then((res) => {
        //if the default currency is null, then don't set it, otherwise setCurrentCurrency
        if (
          res[0].default_currency !== undefined &&
          res[0].default_currency !== null
        ) {
          setCurrentCurrency(res[0].default_currency.code);
        }
        return res[0];
      }),
    {
      onSuccess: (data) => {
        if (
          data.default_currency !== undefined &&
          data.default_currency !== null
        ) {
          setCurrentCurrency(data.default_currency.code);
        }
        const storeOrgObject: IOrgStoreType = {
          organization_id: data.organization_id,
          company_name: data.company_name,
          default_currency: data.default_currency
            ? data.default_currency
            : undefined,
          environment: undefined,
        };

        setOrgInfoToStore(storeOrgObject);
      },
    }
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
      onError: (error: QueryErrors) => {
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
        queryClient.invalidateQueries("organization");
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

      {isLoading ? (
        <div className="mt-10">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="flex flex-col w-6/12 justify-between">
          {mutation.isLoading && <LoadingSpinner />}
          <p className=" text-[16px]">
            <b>Company Name:</b> {org.company_name}
          </p>
          <p className=" text-[16px]">
            <b className="">Default Organization Currency:</b>{" "}
            {org.default_currency !== undefined &&
            org.default_currency !== null ? (
              <Tag>
                {org.default_currency?.name +
                  " " +
                  org.default_currency?.symbol}
              </Tag>
            ) : (
              "N/A"
            )}
          </p>

          <div className="">
            <Button
              onClick={() => setIsEdit(true)}
              className="justify-self-end"
            >
              Edit
            </Button>
          </div>
        </div>
      )}
      <Modal
        title="Edit Organization Settings"
        visible={isEdit}
        onCancel={() => setIsEdit(false)}
        okText="Save"
        onOk={() => {
          if (org.organization_id.length) {
            updateOrg.mutate({
              org_id: org.organization_id,
              default_currency_code: currentCurrency,
            });
            form.resetFields();
          }
          setIsEdit(false);
        }}
      >
        <div className="flex flex-col justify-between">
          <Form
            form={form}
            initialValues={{
              company_name: org?.company_name,
              default_currency: org?.default_currency?.code,
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
              <Input disabled={true} />
            </Form.Item>
            <Form.Item
              label="Default Organization Currency"
              name="default_currency"
            >
              <Select
                onChange={setCurrentCurrency}
                options={pricingUnits?.map((pc) => {
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
