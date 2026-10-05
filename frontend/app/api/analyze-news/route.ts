import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return NextResponse.json({ detail: "No news screenshot uploaded." }, { status: 400 });
    }

    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    const proxyFormData = new FormData();
    proxyFormData.append("file", file);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000);

    const res = await fetch(`${backendUrl}/api/v1/analyze-news`, {
      method: "POST",
      body: proxyFormData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const responseText = await res.text();
    let data;
    try {
      data = JSON.parse(responseText);
    } catch {
      data = { detail: responseText };
    }

    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    return NextResponse.json(
      { detail: `Connection error: ${error.message || "Failed to reach backend"}` },
      { status: 502 }
    );
  }
}
